/**
 * Markdown 代码块栈式解析工具
 *
 * 参考 Python 函数 extract_code_block 的思路实现:
 *   1. 扫描全文所有 fence 行 (```lang / ```)
 *   2. 用栈式配对追踪嵌套代码块
 *   3. 栈归零 = 一个完整代码块闭合
 *
 * 能正确处理:
 *   - 代码块内部包含 ``` 字符串 (行首不匹配 fence)
 *   - 嵌套 fence (每个有 infoString 的 fence 都会进栈)
 *   - 流式中未闭合的代码块
 */

// fence 行信息 (内部接口)
interface FenceInfo {
  start: number
  end: number
  tickLen: number
  infoString: string // 空串 = 闭合 fence
}

// 解析后的代码块 (内部接口)
interface ParsedCodeBlock {
  lang: string
  content: string
  closed: boolean
  blockStart: number
  blockEnd: number
}

/**
 * 从文本中提取 app_name (匹配开头的 "app_name:xxx" 行)
 */
export function extractAppNameFromText(text: string): string | null {
  const match = text.match(/^app_name:\s*(.+?)(?:\n|$)/)
  return match ? match[1].trim() : null
}

/**
 * 扫描全文,找到所有 fence 行
 * fence 正则说明:
 *   ^[ \t]{0,3}(`{3,})([^\n`]*)(?:[ \t]*)\n?
 *   - group[2] 必须用贪婪 * 不能用 *!
 *   - 非贪婪 *? 会让 group[2] 永远匹配 0 个字符,
 *     导致 ```html 和 ``` 都被当成闭合 fence
 */
function scanFences(text: string): FenceInfo[] {
  const fences: FenceInfo[] = []
  const fenceRegex = /^[ \t]{0,3}(`{3,})([^\n`]*)(?:[ \t]*)\n?/gm
  let m: RegExpExecArray | null
  while ((m = fenceRegex.exec(text)) !== null) {
    fences.push({
      start: m.index,
      end: m.index + m[0].length,
      tickLen: m[1].length,
      infoString: m[2].trim(),
    })
  }
  return fences
}

/**
 * 栈式解析所有代码块 (已闭合 + 未闭合)
 */
function parseAllCodeBlocks(text: string): ParsedCodeBlock[] {
  const fences = scanFences(text)
  const blocks: ParsedCodeBlock[] = []

  type StackFrame = {
    startIdx: number
    tickLen: number
    lang: string
    contentStart: number
  }
  const stack: StackFrame[] = []

  for (let i = 0; i < fences.length; i++) {
    const f = fences[i]

    if (f.infoString === '') {
      // 无 info string → 闭合
      if (stack.length > 0) {
        const top = stack.pop()!
        blocks.push({
          lang: top.lang,
          content: text.slice(top.contentStart, f.start),
          closed: true,
          blockStart: fences[top.startIdx].start,
          blockEnd: f.end,
        })
      }
    } else {
      // 有 info string → 新代码块开始(进栈)
      stack.push({
        startIdx: i,
        tickLen: f.tickLen,
        lang: f.infoString.toLowerCase(),
        contentStart: f.end,
      })
    }
  }

  // 栈中剩余 = 未闭合的代码块
  for (const frame of stack) {
    blocks.push({
      lang: frame.lang,
      content: text.slice(frame.contentStart),
      closed: false,
      blockStart: fences[frame.startIdx].start,
      blockEnd: text.length,
    })
  }

  return blocks
}

/**
 * 从文本中提取所有已闭合的 markdown 代码块
 */
export function extractCodeBlocks(
  text: string,
): { lang: string; content: string }[] {
  return parseAllCodeBlocks(text)
    .filter((b) => b.closed)
    .map((b) => ({ lang: b.lang, content: b.content }))
}

/**
 * 从文本中提取未闭合的 markdown 代码块 (流式时正在生成的那个)
 */
export function extractOpenCodeBlock(
  text: string,
): { lang: string; content: string } | null {
  const blocks = parseAllCodeBlocks(text)
  const open = blocks.find((b) => !b.closed)
  return open ? { lang: open.lang, content: open.content } : null
}

/**
 * 从文本中提取描述 (去掉 app_name 行和所有代码块后的纯文本)
 * 包括已闭合的和流式中未闭合的
 */
export function extractDescription(text: string): string {
  let result = text.replace(/^app_name:\s*.+?(?:\n|$)/, '')

  const blocks = parseAllCodeBlocks(result)
  // 按 blockStart 降序排,从尾部删起(避免索引偏移)
  blocks.sort((a, b) => b.blockStart - a.blockStart)
  for (const b of blocks) {
    result = result.slice(0, b.blockStart) + result.slice(b.blockEnd)
  }

  return result.trim()
}
