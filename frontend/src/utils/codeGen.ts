/**
 * CodeGen 相关接口定义 + 文本解析 + 辅助函数
 */

import {
  extractAppNameFromText,
  extractCodeBlocks,
  extractOpenCodeBlock,
  extractDescription,
} from './markdownCodeBlocks'

/** 代码文件 */
export interface CodeFile {
  name: string
  label: string
  content: string
  lang?: string
}

/** 代码生成结果 */
export interface CodeGenResult {
  app_name: string
  description: string
  files: CodeFile[]
  currentFileIndex: number
  isComplete: boolean
}

const LANG_TO_FILE_NAME: Record<string, string> = {
  html: 'html_code', htm: 'html_code',
  css: 'css_code',
  javascript: 'js_code', js: 'js_code',
  vue: 'vue_code',
  react: 'react_code', jsx: 'react_code',
  python: 'python_code', py: 'python_code',
  ts: 'ts_code', typescript: 'ts_code',
  json: 'json_code',
  markdown: 'md_code', md: 'md_code',
  shell: 'shell_code', bash: 'shell_code',
}

const LANG_TO_LABEL: Record<string, string> = {
  html: 'HTML', htm: 'HTML',
  css: 'CSS',
  javascript: 'JavaScript', js: 'JavaScript',
  vue: 'Vue',
  react: 'React', jsx: 'React',
  python: 'Python', py: 'Python',
  ts: 'TypeScript', typescript: 'TypeScript',
  json: 'JSON',
  markdown: 'Markdown', md: 'Markdown',
  shell: 'Shell', bash: 'Shell',
}

/** 根据代码块语言推断文件名 */
export function getFileNameByLang(lang: string): string {
  return LANG_TO_FILE_NAME[lang] || `${lang}_code`
}

/** 根据代码块语言推断显示标签 */
export function getFileLabelByLang(lang: string): string {
  return LANG_TO_LABEL[lang] || lang.toUpperCase()
}

/** 综合解析纯文本为 CodeGenResult */
export function parseTextToCodeGen(
  text: string,
  isComplete: boolean,
): CodeGenResult {
  const app_name = extractAppNameFromText(text) || ''
  const description = extractDescription(text)
  const closedBlocks = extractCodeBlocks(text)
  const openBlock = isComplete ? null : extractOpenCodeBlock(text)

  const files: CodeFile[] = []

  for (const block of closedBlocks) {
    let finalName = getFileNameByLang(block.lang)
    let counter = 1
    while (files.some((f) => f.name === finalName)) {
      finalName = `${getFileNameByLang(block.lang)}_${counter}`
      counter++
    }
    files.push({
      name: finalName,
      label: getFileLabelByLang(block.lang),
      content: block.content,
    })
  }

  if (openBlock) {
    let finalName = getFileNameByLang(openBlock.lang)
    let counter = 1
    while (files.some((f) => f.name === finalName)) {
      finalName = `${getFileNameByLang(openBlock.lang)}_${counter}`
      counter++
    }
    files.push({
      name: finalName,
      label: getFileLabelByLang(openBlock.lang),
      content: openBlock.content,
    })
  }

  return { app_name, description, files, currentFileIndex: 0, isComplete }
}

/** 将 ISO 时间字符串转换为后端期望的格式 YYYY&mm&dd&HH&MM&SS */
export function formatTimeForApi(isoStr: string): string {
  if (!isoStr) return ''
  const match = isoStr.match(
    /(\d{4})[-&:\/](\d{1,2})[-&:\/](\d{1,2})[T\s]?(\d{1,2})[:&](\d{1,2})[:&](\d{1,2})/,
  )
  if (match) {
    const [, y, mo, d, h, mi, s] = match
    const pad = (n: string) => (n.length === 1 ? '0' + n : n)
    return `${y}&${pad(mo)}&${pad(d)}&${pad(h)}&${pad(mi)}&${pad(s)}`
  }
  return isoStr
}
