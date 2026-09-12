<template>
  <div id="appChatPage">
    <!-- 顶部栏 -->
    <div class="header-bar">
      <div class="header-left">
        <h1 class="app-name">{{ appInfo?.app_name || '网站生成器' }}</h1>
        <a-select
          v-model:value="selectedCodeGenType"
          class="code-gen-type-selector"
          size="small"
          disabled
        >
          <a-select-option
            v-for="opt in codeGenTypeOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </a-select-option>
        </a-select>
      </div>
      <div class="header-right">
        <a-button type="default" @click="showAppDetail">
          <template #icon>
            <InfoCircleOutlined />
          </template>
          应用详情
        </a-button>
        <a-button
          type="primary"
          ghost
          @click="downloadCode"
          :loading="downloading"
          :disabled="!isOwner"
        >
          <template #icon>
            <DownloadOutlined />
          </template>
          下载代码
        </a-button>
        <a-button type="primary" @click="deployApp" :loading="deploying">
          <template #icon>
            <CloudUploadOutlined />
          </template>
          部署
        </a-button>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content">
      <!-- 左侧对话区域 -->
      <div class="chat-section">
        <!-- 消息区域 -->
        <div class="messages-container" ref="messagesContainer">
          <!-- 加载更多按钮 -->
          <div v-if="hasMoreHistory" class="load-more-container">
            <a-button type="link" @click="loadMoreHistory" :loading="loadingHistory" size="small">
              加载更多历史消息
            </a-button>
          </div>
          <div v-for="(message, index) in messages" :key="index" class="message-item">
            <div v-if="message.type === 'user'" class="user-message">
              <div class="message-content">{{ message.content }}</div>
              <div class="message-avatar">
                <a-avatar :src="loginUserStore.loginUser.user_avatar" />
              </div>
            </div>
            <div v-else class="ai-message">
              <div class="message-avatar">
                <a-avatar :src="aiAvatar" />
              </div>
              <div class="message-content">
                <!-- 交织渲染:按时间顺序渲染 fragments,实现即时文本和耗时任务交错显示 -->
                <template v-if="message.fragments && message.fragments.length > 0">
                  <template v-for="(f, i) in message.fragments" :key="i">
                    <MarkdownRenderer
                      v-if="f.kind === 'text' && f.text"
                      :content="f.text"
                    />
                    <TaskCard
                      v-else-if="f.kind === 'task' && message.tasksMap && message.tasksMap[f.task_id!]"
                      :task="message.tasksMap[f.task_id!]"
                    />
                  </template>
                </template>

                <!-- Fallback:没有 fragments 时(纯代码块消息或历史消息) -->
                <template v-else>
                  <!-- 代码生成类消息:只展示 description 文本(已过滤 app_name 和代码块) -->
                  <template v-if="message.codeGen">
                    <MarkdownRenderer v-if="message.content" :content="message.content" />
                    <div v-else class="ai-description-empty">（请查看下方代码面板）</div>
                  </template>
                  <!-- 普通消息 -->
                  <MarkdownRenderer v-else-if="message.content" :content="message.content" />
                </template>

                <div v-if="message.loading" class="loading-indicator">
                  <a-spin size="small" />
                  <span>AI 正在思考...</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 用户消息输入框（固定在中间） -->
        <div class="input-container">
          <div class="input-wrapper">
            <a-tooltip v-if="!isOwner" title="无法在别人的作品下对话哦~" placement="top">
              <a-textarea
                v-model:value="userInput"
                :placeholder="getInputPlaceholder()"
                :rows="4"
                :maxlength="1000"
                @keydown.enter.prevent="sendMessage"
                :disabled="isGenerating || !isOwner"
              />
            </a-tooltip>
            <a-textarea
              v-else
              v-model:value="userInput"
              :placeholder="getInputPlaceholder()"
              :rows="4"
              :maxlength="1000"
              @keydown.enter.prevent="sendMessage"
              :disabled="isGenerating"
            />
            <div class="input-actions">
              <a-button
                type="primary"
                @click="sendMessage"
                :loading="isGenerating"
                :disabled="!isOwner"
              >
                <template #icon>
                  <SendOutlined />
                </template>
              </a-button>
            </div>
          </div>
        </div>

        <!-- 选中元素信息展示 -->
        <a-alert
          v-if="selectedElementInfo"
          class="selected-element-alert"
          type="info"
          closable
          @close="clearSelectedElement"
        >
          <template #message>
            <div class="selected-element-info">
              <div class="element-header">
                <span class="element-tag">
                  选中元素：{{ selectedElementInfo.tagName.toLowerCase() }}
                </span>
                <span v-if="selectedElementInfo.id" class="element-id">
                  #{{ selectedElementInfo.id }}
                </span>
                <span v-if="selectedElementInfo.className" class="element-class">
                  .{{ selectedElementInfo.className.split(' ').join('.') }}
                </span>
              </div>
              <div class="element-details">
                <div v-if="selectedElementInfo.textContent" class="element-item">
                  内容: {{ selectedElementInfo.textContent.substring(0, 50) }}
                  {{ selectedElementInfo.textContent.length > 50 ? '...' : '' }}
                </div>
                <div v-if="selectedElementInfo.pagePath" class="element-item">
                  页面路径: {{ selectedElementInfo.pagePath }}
                </div>
                <div class="element-item">
                  选择器:
                  <code class="element-selector-code">{{ selectedElementInfo.selector }}</code>
                </div>
              </div>
            </div>
          </template>
        </a-alert>

        <!-- 可拖拽分割线 -->
        <div
          v-if="latestCodeGen"
          class="resize-handle"
          @mousedown="startResize"
          :class="{ active: isResizing }"
        ></div>

        <!-- 独立代码展示面板（最下面，可调节高度） -->
        <div
          v-if="latestCodeGen"
          ref="codePanelRef"
          class="code-viewer-panel"
          :style="codePanelStyle"
        >
          <div class="codeGen-viewer">
            <div class="codeGen-toolbar">
              <span class="codeGen-count" v-if="latestCodeGen.isComplete"
                >共生成 {{ latestCodeGen.files.length }} 个文件</span
              >
              <span class="codeGen-count streaming" v-else>正在生成代码...</span>
              <a-select
                v-model:value="latestCodeGen.currentFileIndex"
                class="codeGen-select"
                size="small"
              >
                <a-select-option
                  v-for="(file, idx) in latestCodeGen.files"
                  :key="file.name"
                  :value="idx"
                >
                  {{ file.label }}
                  <span
                    v-if="idx === 0 && !latestCodeGen.isComplete"
                    class="streaming-badge"
                  >
                    · 流式中</span
                  >
                </a-select-option>
              </a-select>
            </div>
            <div class="codeGen-codeBlock">
              <pre class="hljs"><code v-html="getHighlightedCodeFromGen(latestCodeGen)" /></pre>
            </div>
          </div>
        </div>
      </div>
      <!-- 右侧网页展示区域 -->
      <div class="preview-section">
        <div class="preview-header">
          <h3>生成后的网页展示</h3>
          <div class="preview-actions">
            <a-button
              v-if="isOwner && previewUrl"
              type="link"
              :danger="isEditMode"
              @click="toggleEditMode"
              :class="{ 'edit-mode-active': isEditMode }"
              style="padding: 0; height: auto; margin-right: 12px"
            >
              <template #icon>
                <EditOutlined />
              </template>
              {{ isEditMode ? '退出编辑' : '编辑模式' }}
            </a-button>
            <a-button v-if="previewUrl" type="link" @click="openInNewTab">
              <template #icon>
                <ExportOutlined />
              </template>
              新窗口打开
            </a-button>
          </div>
        </div>
        <div class="preview-content">
          <div v-if="noPreviewAvailable" class="preview-placeholder">
            <div class="placeholder-icon">📄</div>
            <p>当前内容不支持预览</p>
          </div>
          <div v-else-if="!previewUrl && !isGenerating" class="preview-placeholder">
            <div class="placeholder-icon">🌐</div>
            <p>网站文件生成完成后将在这里展示</p>
          </div>
          <div v-else-if="isGenerating && hasCodeBlockInStream" class="preview-loading">
            <a-spin size="large" />
            <p>正在生成网站...</p>
          </div>
          <iframe
            v-else
            :src="previewUrl"
            class="preview-iframe"
            frameborder="0"
            @load="onIframeLoad"
          ></iframe>
        </div>
      </div>
    </div>

    <!-- 应用详情弹窗 -->
    <AppDetailModal
      v-model:open="appDetailVisible"
      :app="appInfo"
      :show-actions="isOwner || isAdmin"
      @edit="editApp"
      @delete="deleteApp"
    />

    <!-- 部署成功弹窗 -->
    <DeploySuccessModal
      v-model:open="deployModalVisible"
      :deploy-url="deployUrl"
      @open-site="openDeployedSite"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useLoginUserStore } from '@/stores/loginUser'
import {
  deleteApp as deleteAppApi,
  deployApp as deployAppApi,
  getAppVoById,
} from '@/api/appController'
import { listAppChatHistory } from '@/api/chatHistoryController'
import { CodeGenTypeEnum, CODE_GEN_TYPE_OPTIONS } from '@/utils/codeGenTypes'
import request from '@/request'

import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import AppDetailModal from '@/components/AppDetailModal.vue'
import DeploySuccessModal from '@/components/DeploySuccessModal.vue'
import TaskCard from '@/components/TaskCard.vue'
import aiAvatar from '@/assets/aiAvatar.png'
import { API_BASE_URL, getStaticListUrl, resolvePreviewUrlFromList } from '@/config/env'
import { type ElementInfo, VisualEditor } from '@/utils/visualEditor'
import 'highlight.js/styles/github-dark.css'
import hljs from 'highlight.js/lib/common'


import {
  CloudUploadOutlined,
  DownloadOutlined,
  EditOutlined,
  ExportOutlined,
  InfoCircleOutlined,
  SendOutlined,
} from '@ant-design/icons-vue'

const route = useRoute()
const router = useRouter()
const loginUserStore = useLoginUserStore()
const TOKEN_KEY = 'token'

// 代码文件接口
interface CodeFile {
  name: string
  label: string
  content: string
  lang?: string // 新增:代码块的原始语言标签(可选)
}

// 代码生成结果接口
interface CodeGenResult {
  app_name: string
  description: string
  files: CodeFile[]
  currentFileIndex: number
  isComplete: boolean
}

// ======= 纯文本格式解析工具函数 =======
// 后端现在返回纯文本流,可能包含:
//  - 开头的 "app_name:xxx\n\n" 行
//  - 中间的自然语言描述
//  - markdown 代码块: ```lang\n...content...```

// 从文本中提取 app_name (匹配开头的 "app_name:xxx" 行)
function extractAppNameFromText(text: string): string | null {
  const match = text.match(/^app_name:\s*(.+?)(?:\n|$)/)
  return match ? match[1].trim() : null
}

// ===== Markdown 代码块栈式解析底层 =====
// fence_pattern: 匹配任意 fence 行,支持嵌套 ```
//   ^[ \t]{0,3}(`{3,})([^\n`]*?)(?:[ \t]*)\n?
//   - group[1]: 反引号串 (`` ` ```、`` ``` ``...)
//   - group[2]: info string (语言标签),空字符串表示闭合 fence
interface FenceInfo {
  start: number        // fence 行在全文中的起始位置
  end: number          // fence 行结尾(含换行)
  tickLen: number      // 反引号数量
  infoString: string   // 语言标签(trim 后),空串 = 闭合
}

interface ParsedCodeBlock {
  lang: string
  content: string
  closed: boolean       // true = 已闭合; false = 未闭合(流式中)
  blockStart: number    // ```lang 开始位置
  blockEnd: number      // 闭合 ``` 结束位置(未闭合则 = 全文末尾)
}

// 扫描全文,找到所有 fence 行
function scanFences(text: string): FenceInfo[] {
  const fences: FenceInfo[] = []
  // 注意: group[2] 必须用贪婪 * 不能用 *!
  // 非贪婪 *? 会让 "([^\n`]*?)" 永远只匹配 0 个字符,
  // 导致 ```html 和 ``` 两种 fence 的 infoString 都是 "",全部被误判为闭合。
  // 贪婪 * 下: ```html\n 会贪婪吃掉 "html" → infoString="html" ✅
  //           ```\n      因下一个字符就是 \n 所以匹配 0 → infoString="" ✅
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

// 栈式解析所有代码块
function parseAllCodeBlocks(text: string): ParsedCodeBlock[] {
  const fences = scanFences(text)
  const blocks: ParsedCodeBlock[] = []

  type StackFrame = {
    startIdx: number        // 对应 fences 数组的 index
    tickLen: number
    lang: string
    contentStart: number    // 内容起始位置 = 起始 fence 的 end
  }
  const stack: StackFrame[] = []

  for (let i = 0; i < fences.length; i++) {
    const f = fences[i]

    if (f.infoString === '') {
      // 无 info string → 闭合
      if (stack.length > 0) {
        // 匹配栈顶
        const top = stack.pop()!
        blocks.push({
          lang: top.lang,
          content: text.slice(top.contentStart, f.start),
          closed: true,
          blockStart: fences[top.startIdx].start,
          blockEnd: f.end,
        })
      }
      // 栈空时出现无 info string 的 fence,是孤立闭合 fence,忽略
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

  // 栈中剩余 = 未闭合的代码块(流式中正在生成的)
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

// 从文本中提取所有已闭合的 markdown 代码块
function extractCodeBlocks(text: string): { lang: string; content: string }[] {
  return parseAllCodeBlocks(text)
    .filter((b) => b.closed)
    .map((b) => ({ lang: b.lang, content: b.content }))
}

// 从文本中提取未闭合的 markdown 代码块(流式时正在生成的那个)
function extractOpenCodeBlock(text: string): { lang: string; content: string } | null {
  const blocks = parseAllCodeBlocks(text)
  const open = blocks.find((b) => !b.closed)
  return open ? { lang: open.lang, content: open.content } : null
}

// 从文本中提取描述(去掉 app_name 行和所有代码块后的纯文本)
// 注意:也要去掉未闭合的流式代码块(最后一个 ```lang\n 后面的全部内容)
function extractDescription(text: string): string {
  // 先去掉 app_name:xxx 行
  let result = text.replace(/^app_name:\s*.+?(?:\n|$)/, '')

  // 用栈式解析找到所有代码块范围,从后往前删除(避免索引偏移)
  const blocks = parseAllCodeBlocks(result)
  // 按 blockStart 降序排,从尾部删起
  blocks.sort((a, b) => b.blockStart - a.blockStart)
  for (const b of blocks) {
    result = result.slice(0, b.blockStart) + result.slice(b.blockEnd)
  }

  return result.trim()
}

// 根据代码块语言推断文件名(唯一标识)
function getFileNameByLang(lang: string): string {
  const langMap: Record<string, string> = {
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
  return langMap[lang] || `${lang}_code`
}

// 根据代码块语言推断显示标签
function getFileLabelByLang(lang: string): string {
  const labelMap: Record<string, string> = {
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
  return labelMap[lang] || lang.toUpperCase()
}

// 综合解析纯文本为 CodeGenResult
function parseTextToCodeGen(text: string, isComplete: boolean): CodeGenResult {
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

// 将 ISO 时间字符串转换为后端期望的格式 YYYY&mm&dd&HH&MM&SS
function formatTimeForApi(isoStr: string): string {
  if (!isoStr) return ''
  // 匹配 ISO 格式中的年月日时分秒部分，兼容带 T 分隔符和无 T 的情况
  const match = isoStr.match(/(\d{4})[-&:\/](\d{1,2})[-&:\/](\d{1,2})[T\s]?(\d{1,2})[:&](\d{1,2})[:&](\d{1,2})/)
  if (match) {
    const [, y, mo, d, h, mi, s] = match
    // 补零
    const pad = (n: string) => n.length === 1 ? '0' + n : n
    return `${y}&${pad(mo)}&${pad(d)}&${pad(h)}&${pad(mi)}&${pad(s)}`
  }
  return isoStr
}

// (旧函数 tryParseCodeGenResult / tryExtractDescription 已移除,统一使用 parseTextToCodeGen)

// 应用信息
const appInfo = ref<API.AppVO>()
const appId = ref<any>()

// 代码生成类型选择
const codeGenTypeOptions = CODE_GEN_TYPE_OPTIONS
const selectedCodeGenType = ref<string>(CodeGenTypeEnum.HTML)

// 耗时任务条目(后端 SSE event 类型: task_start / task_end / web_search / web_search_done)
export interface TaskItem {
  task_id: string
  type: string            // 'tool_call' | 'web_search' | 其他扩展类型
  status: 'running' | 'done'
  info: string            // 后端返回的 markdown 说明
  extra?: Record<string, unknown>
}

// 消息片段:支持即时文本与耗时任务交织显示
export type MessageFragment =
  | { kind: 'text'; text: string }
  | { kind: 'task'; task_id: string }

// 对话相关
interface Message {
  type: 'user' | 'ai'
  content?: string         // 完整文本(已过滤 app_name 和代码块),给历史回显 fallback 用
  loading?: boolean
  create_time?: string
  codeGen?: CodeGenResult
  fragments?: MessageFragment[]              // 按时间顺序排列的片段(交织显示核心)
  tasksMap?: Record<string, TaskItem>        // task_id → TaskItem,方便按 id 查当前状态
}

const messages = ref<Message[]>([])
const userInput = ref('')
const isGenerating = ref(false)
const hasCodeBlockInStream = ref(false) // 标记当前 AI 回复中是否已出现代码块(懒触发预览用)
const messagesContainer = ref<HTMLElement>()

// 代码面板拖拽调节高度相关
const codePanelRef = ref<HTMLElement>()
const isResizing = ref(false)
const codePanelHeight = ref<number | null>(null) // null = 自适应
const START_RESIZE_Y = ref(0)
const START_PANEL_HEIGHT = ref(0)

const MIN_PANEL_HEIGHT = 120
const MAX_PANEL_RATIO = 0.5 // 最多占 50%

// 代码面板的动态样式:
// - 默认(null):自适应内容高度,max-height 50%
// - 拖拽后(有固定值):固定高度 + flex:none(覆盖 CSS flex:0 0 auto)
const codePanelStyle = computed<Record<string, string>>(() => {
  if (codePanelHeight.value !== null) {
    return { height: codePanelHeight.value + 'px', flex: 'none' }
  }
  return {}
})

// 开始拖拽
function startResize(e: MouseEvent) {
  isResizing.value = true
  START_RESIZE_Y.value = e.clientY
  if (codePanelRef.value) {
    START_PANEL_HEIGHT.value = codePanelRef.value.getBoundingClientRect().height
  }
  document.addEventListener('mousemove', doResize)
  document.addEventListener('mouseup', stopResize)
  document.body.style.cursor = 'row-resize'
  document.body.style.userSelect = 'none'
}

// 拖拽中
function doResize(e: MouseEvent) {
  if (!isResizing.value || !codePanelRef.value) return
  const chatSection = codePanelRef.value.parentElement
  if (!chatSection) return

  const delta = START_RESIZE_Y.value - e.clientY // 鼠标向上拖 → 面板变高
  const sectionHeight = chatSection.getBoundingClientRect().height
  const maxHeight = sectionHeight * MAX_PANEL_RATIO
  const minHeight = MIN_PANEL_HEIGHT

  let newHeight = START_PANEL_HEIGHT.value + delta
  newHeight = Math.max(minHeight, Math.min(maxHeight, newHeight))
  codePanelHeight.value = Math.round(newHeight)
}

// 停止拖拽
function stopResize() {
  isResizing.value = false
  document.removeEventListener('mousemove', doResize)
  document.removeEventListener('mouseup', stopResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// 找到最新的带有效 codeGen(有代码文件)的 AI 消息,用于下半部分独立代码面板展示
const latestCodeGen = computed(() => {
  const msgs = messages.value
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].type === 'ai' && msgs[i].codeGen && msgs[i].codeGen.files.length > 0) {
      return msgs[i].codeGen
    }
  }
  return null
})

// 对话历史相关
const loadingHistory = ref(false)
const hasMoreHistory = ref(false)
const lastCreateTime = ref<string>()
const historyLoaded = ref(false)

// 预览相关
const previewUrl = ref('')
const previewReady = ref(false)
const noPreviewAvailable = ref(false)

// 部署相关
const deploying = ref(false)
const deployModalVisible = ref(false)
const deployUrl = ref('')

// 下载相关
const downloading = ref(false)

// 可视化编辑相关
const isEditMode = ref(false)
const selectedElementInfo = ref<ElementInfo | null>(null)
const visualEditor = new VisualEditor({
  onElementSelected: (elementInfo: ElementInfo) => {
    selectedElementInfo.value = elementInfo
  },
})

// 权限相关
const isOwner = computed(() => {
  return appInfo.value?.user_id === loginUserStore.loginUser.id
})

const isAdmin = computed(() => {
  return loginUserStore.loginUser.user_role === 'admin'
})

// 应用详情相关
const appDetailVisible = ref(false)

// 显示应用详情
const showAppDetail = () => {
  appDetailVisible.value = true
}

// 加载对话历史
const loadChatHistory = async (isLoadMore = false) => {
  if (!appId.value || loadingHistory.value) return
  loadingHistory.value = true
  try {
    const params: API.listAppChatHistoryParams = {
      app_id: appId.value,
      per_page: 10,
    }
    // 如果是加载更多，传递最后一条消息的创建时间作为游标
    if (isLoadMore && lastCreateTime.value) {
      params.last_create_time = lastCreateTime.value
    }
    const res = await listAppChatHistory(params)
    if (res.data.code === 20000 && res.data.data) {
      const chatHistories = res.data.data.chat_records || []
      if (chatHistories.length > 0) {
        // 将对话历史转换为消息格式，并按时间正序排列（老消息在前）
        const historyMessages: Message[] = chatHistories
          .map((chat) => {
            const base: Message = {
              type: (chat.message_type === 'user' ? 'user' : 'ai') as 'user' | 'ai',
              content: chat.message || '',
              create_time: chat.create_time,
            }
            // AI 消息:用新的纯文本markdown解析逻辑
            if (base.type === 'ai' && chat.message) {
              const parsed = parseTextToCodeGen(chat.message, true)
              base.content = parsed.description
              if (parsed.files.length > 0 || parsed.app_name) {
                base.codeGen = parsed
              }
            }
            return base
          })
        // TODO 调试待删除
        console.log('historyMessages: ', historyMessages)
        if (isLoadMore) {
          // 加载更多时，将历史消息添加到开头
          messages.value.unshift(...historyMessages)
        } else {
          // 初始加载，直接设置消息列表
          messages.value = historyMessages
        }
        // 更新游标
        lastCreateTime.value = formatTimeForApi(<string>chatHistories[chatHistories.length - 1]?.create_time)
        // TODO 调试待删除
        console.log('lastCreateTime: ', lastCreateTime.value)
        // 检查是否还有更多历史
        hasMoreHistory.value = chatHistories.length === 10
      } else {
        hasMoreHistory.value = false
      }
      historyLoaded.value = true
    }
  } catch (error) {
    console.error('加载对话历史失败：', error)
    message.error('加载对话历史失败')
  } finally {
    loadingHistory.value = false
  }
}

// 加载更多历史消息
const loadMoreHistory = async () => {
  await loadChatHistory(true)
}

// 获取应用信息
const fetchAppInfo = async () => {
  const id = route.params.id as string
  if (!id) {
    message.error('应用ID不存在')
    router.push('/')
    return
  }

  appId.value = id

  try {
    const res = await getAppVoById({ id: id as unknown as number })
    if (res.data.code === 20000 && res.data.data) {
      appInfo.value = res.data.data

      // 初始化代码生成类型选择
      if (appInfo.value.code_gen_type) {
        selectedCodeGenType.value = appInfo.value.code_gen_type
      }

      // 先加载对话历史
      await loadChatHistory()
      // 如果有至少2条对话记录，展示对应的网站
      if (messages.value.length >= 2) {
        updatePreview()
      }
      // 检查是否需要自动发送初始提示词
      // 只有在是自己的应用且没有对话历史时才自动发送
      if (
        appInfo.value.init_prompt &&
        isOwner.value &&
        messages.value.length === 0 &&
        historyLoaded.value
      ) {
        await sendInitialMessage(appInfo.value.init_prompt)
      }
    } else {
      message.error('获取应用信息失败')
      router.push('/')
    }
  } catch (error) {
    console.error('获取应用信息失败：', error)
    message.error('获取应用信息失败')
    router.push('/')
  }
}

// 根据文件名推断语言
// 新格式: html_code / css_code / js_code / vue_code / react_code / python_code / ts_code / json_code / md_code / shell_code ...
function getLanguageByFileName(fileName: string): string {
  // 先尝试从 "xxx_code" 格式里提取前面的 xxx
  const match = fileName.match(/^(.+)_code$/)
  const rawName = match ? match[1] : fileName

  const langMap: Record<string, string> = {
    html: 'html',
    htm: 'html',
    css: 'css',
    js: 'javascript',
    javascript: 'javascript',
    vue: 'html',
    react: 'jsx',
    jsx: 'jsx',
    python: 'python',
    py: 'python',
    ts: 'typescript',
    typescript: 'typescript',
    json: 'json',
    md: 'markdown',
    markdown: 'markdown',
    shell: 'shell',
    bash: 'shell',
  }
  return langMap[rawName] || 'plaintext'
}

// 获取高亮后的代码（从 CodeGenResult 中，供独立代码面板使用）
const getHighlightedCodeFromGen = (codeGen: CodeGenResult): string => {
  if (!codeGen || codeGen.files.length === 0) return ''
  const file = codeGen.files[codeGen.currentFileIndex]
  if (!file) return ''
  const lang = getLanguageByFileName(file.name)
  try {
    if (lang !== 'plaintext' && hljs.getLanguage(lang)) {
      return hljs.highlight(file.content, { language: lang, ignoreIllegals: true }).value
    }
    return hljs.highlightAuto(file.content).value
  } catch {
    return file.content
  }
}

// 发送初始消息
const sendInitialMessage = async (prompt: string) => {
  // 添加用户消息
  messages.value.push({
    type: 'user',
    content: prompt,
  })

  // 添加AI消息占位符
  const aiMessageIndex = messages.value.length
  messages.value.push({
    type: 'ai',
    content: '',
    loading: true,
  })

  await nextTick()
  scrollToBottom()

  // 开始生成
  isGenerating.value = true
  await generateCode(prompt, aiMessageIndex)
}

// 发送消息
const sendMessage = async () => {
  if (!userInput.value.trim() || isGenerating.value) {
    return
  }

  let message = userInput.value.trim()
  // 如果有选中的元素，将元素信息添加到提示词中
  if (selectedElementInfo.value) {
    let elementContext = `\n\n选中元素信息：`
    if (selectedElementInfo.value.pagePath) {
      elementContext += `\n- 页面路径: ${selectedElementInfo.value.pagePath}`
    }
    elementContext += `\n- 标签: ${selectedElementInfo.value.tagName.toLowerCase()}\n- 选择器: ${selectedElementInfo.value.selector}`
    if (selectedElementInfo.value.textContent) {
      elementContext += `\n- 当前内容: ${selectedElementInfo.value.textContent.substring(0, 100)}`
    }
    message += elementContext
  }
  userInput.value = ''
  // 添加用户消息（包含元素信息）
  messages.value.push({
    type: 'user',
    content: message,
  })

  // 发送消息后，清除选中元素并退出编辑模式
  if (selectedElementInfo.value) {
    clearSelectedElement()
    if (isEditMode.value) {
      toggleEditMode()
    }
  }

  // 添加AI消息占位符
  const aiMessageIndex = messages.value.length
  messages.value.push({
    type: 'ai',
    content: '',
    loading: true,
  })

  await nextTick()
  scrollToBottom()

  // 开始生成
  isGenerating.value = true
  await generateCode(message, aiMessageIndex)
}

// 生成代码 - 使用 fetch + ReadableStream 处理 POST 流式响应
const generateCode = async (userMessage: string, aiMessageIndex: number) => {
  let streamCompleted = false
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null
  const aiMessage = messages.value[aiMessageIndex]

  try {
    const baseURL = request.defaults.baseURL || API_BASE_URL
    const token = localStorage.getItem(TOKEN_KEY) || ''

    const response = await fetch(`${baseURL}/code/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        init_prompt: userMessage,
        code_gen_type: selectedCodeGenType.value,
        app_id: appId.value,
      }),
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let rawContentBuffer = ''

    // ⚠️ 关键:在任何 SSE 事件到达之前就初始化 fragments 和 tasksMap
    // 否则第一条 message 事件到达时 fragments 还是 undefined,
    // 前面的即时文本会全部丢失,只有 task 事件先到达时才会被初始化
    aiMessage.fragments = []
    aiMessage.tasksMap = {}

    // 文本边界快照:记录上一个 task 事件到达时 description 的长度
    // 用于在 task 之后正确切分出"新增的文本片段",避免 task 后的 text fragment
    // 把 task 之前的内容又重复存一遍
    let textBoundary = 0

    const finalizeGeneration = () => {
      streamCompleted = true
      isGenerating.value = false

      const result = parseTextToCodeGen(rawContentBuffer, true)
      aiMessage.loading = false

      // 同步更新页面顶部的 app_name(无论是否有代码块)
      if (result.app_name && appInfo.value && appInfo.value.app_name !== result.app_name) {
        appInfo.value.app_name = result.app_name
      }

      if (result.files.length > 0) {
        // 有代码块 → 设为 codeGen 消息,并刷新预览
        aiMessage.codeGen = result
        aiMessage.content = result.description  // description 已过 extractDescription 过滤
        setTimeout(async () => {
          await fetchAppInfo()
          updatePreview()
        }, 1000)
      } else {
        // 纯文本回复 → 必须过 extractDescription 过滤 app_name 行
        // (不能直接用 rawContentBuffer,否则 app_name:xxx 会泄漏到聊天里)
        aiMessage.content = extractDescription(rawContentBuffer)
      }

      // 重置懒加载标志
      hasCodeBlockInStream.value = false
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        if (!streamCompleted) finalizeGeneration()
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split('\n\n')
      buffer = events.pop() || ''

      for (const eventBlock of events) {
        const lines = eventBlock.split('\n')
        let eventType = 'message'
        let dataLines: string[] = []
        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).trim())
          }
        }
        const dataStr = dataLines.join('\n')
        if (!dataStr) continue

        if (eventType === 'done') {
          finalizeGeneration()
          continue
        }

        if (eventType === 'error') {
          try {
            const err = JSON.parse(dataStr)
            aiMessage.content = `❌ ${err.message || '生成过程中出现错误'}`
            aiMessage.loading = false
            message.error(err.message || '生成过程中出现错误')
          } catch {
            handleError(new Error('服务器返回错误'), aiMessageIndex)
          }
          streamCompleted = true
          isGenerating.value = false
          continue
        }

        // ======== 耗时任务事件 ========
        // 后端 event 类型: task_start / task_end / web_search / web_search_done
        // 统一数据格式: { task_id, info, extra }
        const TASK_START_TYPES = ['task_start', 'web_search']
        const TASK_END_TYPES = ['task_end', 'web_search_done']
        const taskEventPrefix = eventType.replace(/_start$/, '').replace(/_end$/, '').replace(/_done$/, '')
        const isTaskStart = TASK_START_TYPES.includes(eventType)
        const isTaskEnd = TASK_END_TYPES.includes(eventType)

        if (isTaskStart || isTaskEnd) {
          let taskData: { task_id: string; info: string; extra?: Record<string, unknown> } | null = null
          try {
            taskData = JSON.parse(dataStr)
          } catch {
            // dataStr 不是 JSON,忽略
          }

          if (taskData && taskData.task_id) {
            // 懒初始化
            if (!aiMessage.fragments) aiMessage.fragments = []
            if (!aiMessage.tasksMap) aiMessage.tasksMap = {}

            const taskId = taskData.task_id

            // ====== 在 push 任何 task fragment 之前,先更新 textBoundary ======
            // 因为每个 task 都是一个文本边界:task 之前的 description 长度
            // 就是上一个 text fragment 的"截止位置",task 之后的新 token
            // 应该被放进全新的 text fragment 里
            const currentDesc = extractDescription(rawContentBuffer)
            textBoundary = currentDesc.length

            if (isTaskStart) {
              if (!aiMessage.tasksMap[taskId]) {
                aiMessage.fragments.push({ kind: 'task', task_id: taskId })
                aiMessage.tasksMap[taskId] = {
                  task_id: taskId,
                  type: taskEventPrefix,
                  status: 'running',
                  info: taskData.info || '',
                  extra: taskData.extra,
                }
              } else {
                const t = aiMessage.tasksMap[taskId]
                t.info = taskData.info || t.info
                t.status = 'running'
              }
            } else {
              if (aiMessage.tasksMap[taskId]) {
                const t = aiMessage.tasksMap[taskId]
                t.status = 'done'
                t.info = taskData.info || t.info
                t.extra = taskData.extra ?? t.extra
              } else {
                aiMessage.fragments.push({ kind: 'task', task_id: taskId })
                aiMessage.tasksMap[taskId] = {
                  task_id: taskId,
                  type: taskEventPrefix,
                  status: 'done',
                  info: taskData.info || '',
                  extra: taskData.extra,
                }
              }
            }
          }
          scrollToBottom()
          continue
        }

        // ======== 常规 message 事件(即时文本 token) ========
        try {
          const parsed = JSON.parse(dataStr)
          if (parsed.d !== undefined && parsed.d !== null) {
            rawContentBuffer += parsed.d
          }
        } catch {
          rawContentBuffer += dataStr
        }

        // 实时同步更新页面顶部的 app_name
        const result = parseTextToCodeGen(rawContentBuffer, false)
        if (result.app_name && appInfo.value && appInfo.value.app_name !== result.app_name) {
          appInfo.value.app_name = result.app_name
        }

        // 维护 fragments 中的 text 片段
        // 关键:用 textBoundary 切分,确保每个 text fragment 只存自己那一段
        const filteredText = result.description  // 已过 extractDescription,过滤了 app_name 和代码块
        const last = aiMessage.fragments[aiMessage.fragments.length - 1]
        if (last && last.kind === 'text') {
          // 最后是 text fragment → 增量更新整个 text(同一连续文本段跨越多个 token)
          last.text = filteredText.slice(textBoundary)
          // textBoundary 本身也要跟着推进(防止 task 到来后再切片时出错)
          // 但其实 textBoundary 只会在 task 事件里重置,这里 slice 是安全的
        } else {
          // 最后是 task fragment(刚 push 过 task),或 fragments 刚初始化还空着
          // → 只取 taskBoundary 之后的"新增部分"push 新的 text fragment
          const newSegment = filteredText.slice(textBoundary)
          if (newSegment) {
            aiMessage.fragments.push({ kind: 'text', text: newSegment })
          }
        }

        if (result.files.length > 0) {
          aiMessage.codeGen = result
          aiMessage.content = result.description
          aiMessage.loading = false
          if (!hasCodeBlockInStream.value) {
            hasCodeBlockInStream.value = true
          }
        } else if (!aiMessage.codeGen) {
          // 还没有代码块 → 纯文本流式,content 用已过滤的 description
          aiMessage.content = result.description
          aiMessage.loading = false
        }

        scrollToBottom()
      }
    }
  } catch (error) {
    console.error('生成代码失败：', error)
    if (!streamCompleted) handleError(error, aiMessageIndex)
  } finally {
    if (reader) {
      try {
        reader.releaseLock()
      } catch {}
    }
  }
}

// 错误处理函数
const handleError = (error: unknown, aiMessageIndex: number) => {
  console.error('生成代码失败：', error)
  messages.value[aiMessageIndex].content = '抱歉，生成过程中出现了错误，请重试。'
  messages.value[aiMessageIndex].loading = false
  message.error('生成失败，请重试')
  isGenerating.value = false
  hasCodeBlockInStream.value = false
}

// 更新预览 - 通过文件列表接口获取 index.html 的真实路径
const updatePreview = async () => {
  if (!appId.value) return
  const codeGenType = selectedCodeGenType.value || CodeGenTypeEnum.HTML
  const listUrl = getStaticListUrl(codeGenType, appId.value)

  try {
    // TODO 调试待删除
    console.log("listUrl: ", listUrl)
    const res = await fetch(listUrl)
    if (res.ok) {
      const data = await res.json()
      // TODO 调试待删除
      console.log("fetch(listUrl)响应json: ", data)
      if (data.code === 20000 && data.data?.files?.length) {
        const resolved = resolvePreviewUrlFromList(data.data.files)
        // TODO 调试待删除
        console.log("resolvePreviewUrlFromList: ", resolved)
        if (resolved) {
          previewUrl.value = resolved
          noPreviewAvailable.value = false
          previewReady.value = true
          return
        }
      }
    }
  } catch (e) {
    console.error('获取预览文件列表失败:', e)
  }
  // 未能获取有效预览
  previewUrl.value = ''
  noPreviewAvailable.value = true
  previewReady.value = true
}

// 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 下载代码（调用后端打包接口）
const downloadCode = async () => {
  if (!appId.value) {
    message.error('应用ID不存在')
    return
  }
  downloading.value = true
  try {
    const baseURL = request.defaults.baseURL || API_BASE_URL
    const token = localStorage.getItem(TOKEN_KEY) || ''
    const url = `${baseURL}/code/app/download/${appId.value}`
    const response = await fetch(url, {
      method: 'GET',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) {
      throw new Error(`下载失败: ${response.status}`)
    }
    // 从 Content-Disposition 获取文件名
    const contentDisposition = response.headers.get('Content-Disposition')
    let fileName = `app-${appId.value}.zip`
    if (contentDisposition) {
      const utf8Match = contentDisposition.match(/filename\*=UTF-8''(.+)/i)
      const directMatch = contentDisposition.match(/filename="?(.+?)"?$/)
      fileName = utf8Match ? decodeURIComponent(utf8Match[1]) : (directMatch?.[1] || fileName)
    }
    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(blobUrl)
    message.success('代码下载成功')
  } catch (error) {
    console.error('下载失败：', error)
    message.error('下载失败，请重试')
  } finally {
    downloading.value = false
  }
}

// 部署应用
const deployApp = async () => {
  if (!appId.value) {
    message.error('应用ID不存在')
    return
  }

  deploying.value = true
  try {
    const res = await deployAppApi({
      app_id: appId.value as unknown as number,
    })

    if (res.data.code === 20000 && res.data.data && res.data.data.deploy_url) {
      deployUrl.value = res.data.data.deploy_url
      deployModalVisible.value = true
      message.success('部署成功')
    } else {
      message.error('部署失败：' + res.data.message)
    }
  } catch (error) {
    console.error('部署失败：', error)
    message.error('部署失败，请重试')
  } finally {
    deploying.value = false
  }
}

// 在新窗口打开预览
const openInNewTab = () => {
  if (previewUrl.value) {
    window.open(previewUrl.value, '_blank')
  }
}

// 打开部署的网站
const openDeployedSite = () => {
  if (deployUrl.value) {
    window.open(deployUrl.value, '_blank')
  }
}

// iframe加载完成
const onIframeLoad = () => {
  previewReady.value = true
  const iframe = document.querySelector('.preview-iframe') as HTMLIFrameElement
  if (iframe) {
    visualEditor.init(iframe)
    visualEditor.onIframeLoad()
  }
}

// 编辑应用
const editApp = () => {
  if (appInfo.value?.id) {
    router.push(`/app/edit/${appInfo.value.id}`)
  }
}

// 删除应用
const deleteApp = async () => {
  if (!appInfo.value?.id) return

  try {
    const res = await deleteAppApi({ id: appInfo.value.id })
    if (res.data.code === 20000) {
      message.success('删除成功')
      appDetailVisible.value = false
      await router.push('/')
    } else {
      message.error('删除失败：' + res.data.message)
    }
  } catch (error) {
    console.error('删除失败：', error)
    message.error('删除失败')
  }
}

// 可视化编辑相关函数
const toggleEditMode = () => {
  // 检查 iframe 是否已经加载
  const iframe = document.querySelector('.preview-iframe') as HTMLIFrameElement
  if (!iframe) {
    message.warning('请等待页面加载完成')
    return
  }
  // 确保 visualEditor 已初始化
  if (!previewReady.value) {
    message.warning('请等待页面加载完成')
    return
  }
  const newEditMode = visualEditor.toggleEditMode()
  isEditMode.value = newEditMode
}

const clearSelectedElement = () => {
  selectedElementInfo.value = null
  visualEditor.clearSelection()
}

const getInputPlaceholder = () => {
  if (selectedElementInfo.value) {
    return `正在编辑 ${selectedElementInfo.value.tagName.toLowerCase()} 元素，描述您想要的修改...`
  }
  return '请描述你想生成的网站，越详细效果越好哦'
}

// 页面加载时获取应用信息
onMounted(() => {
  fetchAppInfo()

  // 监听 iframe 消息
  window.addEventListener('message', (event) => {
    visualEditor.handleIframeMessage(event)
  })
})

// 清理资源
onUnmounted(() => {
  // EventSource 会在组件卸载时自动清理
})
</script>

<style scoped>
#appChatPage {
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 16px;
  background: #fdfdfd;
}

/* 顶部栏 */
.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.code-gen-type-selector {
  min-width: 140px;
}

.code-gen-type-selector :deep(.ant-select-selector) {
  border-radius: 16px;
  font-size: 12px;
}

.app-name {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
}

.header-right {
  display: flex;
  gap: 12px;
}

/* 主要内容区域 */
.main-content {
  flex: 1;
  display: flex;
  gap: 16px;
  padding: 8px;
  overflow: hidden;
}

/* 左侧对话区域 */
.chat-section {
  flex: 2;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.messages-container {
  flex: 1;
  min-height: 0;
  padding: 16px;
  overflow-y: auto;
  scroll-behavior: smooth;
}

.message-item {
  margin-bottom: 12px;
}

.user-message {
  display: flex;
  justify-content: flex-end;
  align-items: flex-start;
  gap: 8px;
}

.ai-message {
  display: flex;
  justify-content: flex-start;
  align-items: flex-start;
  gap: 8px;
}

.message-content {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.5;
  word-wrap: break-word;
}

.user-message .message-content {
  background: #1890ff;
  color: white;
}

.ai-message .message-content {
  background: #f5f5f5;
  color: #1a1a1a;
  padding: 8px 12px;
}

.message-avatar {
  flex-shrink: 0;
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #666;
}

/* 加载更多按钮 */
.load-more-container {
  text-align: center;
  padding: 8px 0;
  margin-bottom: 16px;
}

/* 独立代码展示面板 */
.code-viewer-panel {
  flex: 0 0 auto;          /* 默认:高度由内容决定,不参与 flex 伸展/压缩 */
  max-height: 50%;         /* 最多占 50% */
  padding: 8px 16px 16px;
  display: flex;
  flex-direction: column;
}

.code-viewer-panel .codeGen-viewer {
  display: flex;
  flex-direction: column;
  min-height: 0;           /* 关键:保证子元素 overflow:auto 生效 */
  flex: 1 1 auto;          /* 有固定父级高度时撑满,无固定高度时内容决定 */
}

.codeGen-codeBlock {
  flex: 1 1 auto;          /* 占据剩余空间 */
  min-height: 0;           /* 关键:保证 overflow:auto 生效 */
  overflow: auto;          /* 内容多时滚动 */
}

/* 可拖拽分割线 */
.resize-handle {
  height: 6px;
  cursor: row-resize;
  background: transparent;
  position: relative;
  transition: background 0.2s;
  flex-shrink: 0;
}

.resize-handle::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 40px;
  height: 4px;
  background: #d9d9d9;
  border-radius: 2px;
  transition: background 0.2s, width 0.2s;
}

.resize-handle:hover::before,
.resize-handle.active::before {
  background: #3b82f6;
  width: 56px;
}

.resize-handle:hover {
  background: linear-gradient(to bottom, transparent, rgba(59, 130, 246, 0.15), transparent);
}

/* 输入区域 */
.input-container {
  padding: 16px;
  background: white;
}

.input-wrapper {
  position: relative;
}

.input-wrapper .ant-input {
  padding-right: 50px;
}

.input-actions {
  position: absolute;
  bottom: 8px;
  right: 8px;
}

/* 右侧预览区域 */
.preview-section {
  flex: 3;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e8e8e8;
}

.preview-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.preview-actions {
  display: flex;
  gap: 8px;
}

.preview-content {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.preview-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
}

.placeholder-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.preview-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
}

.preview-loading p {
  margin-top: 16px;
}

.preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
}

.selected-element-alert {
  margin: 0 16px;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .main-content {
    flex-direction: column;
  }

  .chat-section,
  .preview-section {
    flex: none;
    height: 50vh;
  }
}

@media (max-width: 768px) {
  .header-bar {
    padding: 12px 16px;
  }

  .app-name {
    font-size: 16px;
  }

  .main-content {
    padding: 8px;
    gap: 8px;
  }

  .message-content {
    max-width: 85%;
  }

  /* 选中元素信息样式 */
  .selected-element-alert {
    margin: 0 16px;
  }

  .selected-element-info {
    line-height: 1.4;
  }

  .element-header {
    margin-bottom: 8px;
  }

  .element-details {
    margin-top: 8px;
  }

  .element-item {
    margin-bottom: 4px;
    font-size: 13px;
  }

  .element-item:last-child {
    margin-bottom: 0;
  }

  .element-tag {
    font-family: 'Monaco', 'Menlo', monospace;
    font-size: 14px;
    font-weight: 600;
    color: #007bff;
  }

  .element-id {
    color: #28a745;
    margin-left: 4px;
  }

  .element-class {
    color: #ffc107;
    margin-left: 4px;
  }

  .element-selector-code {
    font-family: 'Monaco', 'Menlo', monospace;
    background: #f6f8fa;
    padding: 2px 4px;
    border-radius: 3px;
    font-size: 12px;
    color: #d73a49;
    border: 1px solid #e1e4e8;
  }

  /* 编辑模式按钮样式 */
  .edit-mode-active {
    background-color: #52c41a !important;
    border-color: #52c41a !important;
    color: white !important;
  }

  .edit-mode-active:hover {
    background-color: #73d13d !important;
    border-color: #73d13d !important;
  }
}

/* 代码生成结果样式 */
.code-gen-content {
  max-width: 85% !important;
  width: 100%;
  padding: 12px 16px !important;
}

.codeGen-info {
  margin-bottom: 12px;
}

.codeGen-desc {
  margin: 0;
  font-size: 13px;
  color: #666;
  line-height: 1.6;
}

.codeGen-viewer {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
  background: #1e1e1e;
}

.codeGen-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #2d2d2d;
  border-bottom: 1px solid #3e3e3e;
}

.codeGen-count {
  font-size: 12px;
  color: #ccc;
}

.codeGen-count.streaming {
  color: #4ec9b0;
}

.codeGen-select {
  min-width: 140px;
}

.codeGen-select :deep(.ant-select-selector) {
  background: #3e3e3e !important;
  border-color: #555 !important;
  color: #fff !important;
}

.codeGen-select :deep(.ant-select-selection-item) {
  color: #fff;
}

.codeGen-select :deep(.ant-select-arrow) {
  color: #aaa;
}

.streaming-badge {
  color: #4ec9b0;
  font-size: 11px;
}

.codeGen-codeBlock {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.codeGen-codeBlock pre.hljs {
  margin: 0 !important;
  padding: 16px !important;
  background: #0d1117 !important;
  color: #e6edf3 !important;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre;
  tab-size: 2;
  border-radius: 0;
}

.codeGen-codeBlock pre.hljs code {
  background: transparent !important;
  padding: 0 !important;
  font-family: inherit;
  color: inherit;
}
</style>
