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
          :disabled="isGenerating"
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
                <!-- 代码生成类消息：只展示 description 文本，代码块在独立面板 -->
                <template v-if="message.codeGen">
                  <p v-if="message.codeGen.description">{{ message.codeGen.description }}</p>
                  <div v-if="message.loading" class="loading-indicator">
                    <a-spin size="small" />
                    <span>AI 正在生成代码...</span>
                  </div>
                </template>
                <!-- 普通消息 -->
                <template v-else>
                  <MarkdownRenderer v-if="message.content" :content="message.content" />
                  <div v-if="message.loading" class="loading-indicator">
                    <a-spin size="small" />
                    <span>AI 正在思考...</span>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>

        <!-- 下半部分：独立代码展示面板（展示最新的代码生成结果） -->
        <div v-if="latestCodeGen" class="code-viewer-panel">
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

        <!-- 用户消息输入框 -->
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
          <div v-else-if="isGenerating" class="preview-loading">
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
}

// 代码生成结果接口
interface CodeGenResult {
  app_name: string
  description: string
  files: CodeFile[]
  currentFileIndex: number
  isComplete: boolean
}

// 代码字段名 -> 显示标签映射
const CODE_FIELD_MAP: Record<string, string> = {
  html_code: 'HTML',
  css_code: 'CSS',
  js_code: 'JavaScript',
  vue_code: 'Vue',
  react_code: 'React',
  python_code: 'Python',
}
const CODE_FIELD_ORDER = [
  'html_code',
  'css_code',
  'js_code',
  'vue_code',
  'react_code',
  'python_code',
]

// 从buffer中找到第一个出现的代码字段名
function findFirstCodeField(buffer: string): string | null {
  let firstField = null
  let firstPos = Infinity
  for (const name of CODE_FIELD_ORDER) {
    const pos = buffer.indexOf(`"${name}": "`)
    if (pos !== -1 && pos < firstPos) {
      firstPos = pos
      firstField = name
    }
  }
  return firstField
}

// 从buffer中提取简单字段（app_name/description）的完整值
function extractSimpleField(buffer: string, fieldName: string): string | null {
  const pattern = new RegExp(`"${fieldName}":\\s*"((?:[^"\\\\]|\\\\.)*)"`)
  const match = buffer.match(pattern)
  if (match) return unescapeJson(match[1])
  return null
}

// 从可能不完整的JSON buffer中提取指定字段的部分内容
function extractPartialField(buffer: string, fieldName: string): string | null {
  const keyPattern = `"${fieldName}": "`
  const keyIdx = buffer.indexOf(keyPattern)
  if (keyIdx === -1) return null
  let content = buffer.substring(keyIdx + keyPattern.length)
  if (content.endsWith('\\') && content.length > 0) content = content.slice(0, -1)
  return content
}

// 检查字段值是否完整（有正确的JSON字符串结束）
function isFieldComplete(buffer: string, fieldName: string): boolean {
  const keyPattern = `"${fieldName}": "`
  const keyIdx = buffer.indexOf(keyPattern)
  if (keyIdx === -1) return false
  let pos = keyIdx + keyPattern.length
  while (pos < buffer.length) {
    const ch = buffer[pos]
    if (ch === '\\') {
      pos += 2
      continue
    }
    if (ch === '"') {
      const after = buffer.substring(pos + 1).trimStart()
      if (after.startsWith(',') || after.startsWith('}')) return true
    }
    pos++
  }
  return false
}

// 剥离 markdown 代码块包裹（```json ... ``` 或 ``` ... ```）
function stripMarkdownCodeFence(str: string): string {
  let result = str.trim()
  // 去除开头的 ```json 或 ```
  const startFence = result.match(/^```(?:json|javascript|python|html|css|vue|react)?\s*\n?/i)
  if (startFence) result = result.slice(startFence[0].length)
  // 去除结尾的 ```
  const endFence = result.match(/\n?```\s*$/)
  if (endFence) result = result.slice(0, result.length - endFence[0].length)
  return result.trim()
}

// 简单的JSON字符串反转义
function unescapeJson(str: string): string {
  return str.replace(/\\n/g, '\n').replace(/\\t/g, '\t').replace(/\\"/g, '"').replace(/\\\\/g, '\\')
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

// 尝试解析完整JSON buffer并提取代码生成结果
function tryParseCodeGenResult(buffer: string): CodeGenResult | null {
  try {
    const parsed = JSON.parse(buffer)
    if (parsed && typeof parsed === 'object' && parsed.app_name !== undefined) {
      const files: CodeFile[] = []
      for (const key of Object.keys(parsed)) {
        if (CODE_FIELD_MAP[key] && typeof parsed[key] === 'string') {
          files.push({ name: key, label: CODE_FIELD_MAP[key], content: parsed[key] })
        }
      }
      files.sort((a, b) => CODE_FIELD_ORDER.indexOf(a.name) - CODE_FIELD_ORDER.indexOf(b.name))
      return {
        app_name: parsed.app_name || '',
        description: parsed.description || '',
        files,
        currentFileIndex: 0,
        isComplete: true,
      }
    }
  } catch {}
  return null
}

// 应用信息
const appInfo = ref<API.AppVO>()
const appId = ref<any>()

// 代码生成类型选择
const codeGenTypeOptions = CODE_GEN_TYPE_OPTIONS
const selectedCodeGenType = ref<string>(CodeGenTypeEnum.HTML)

// 对话相关
interface Message {
  type: 'user' | 'ai'
  content?: string
  loading?: boolean
  create_time?: string
  codeGen?: CodeGenResult
}

const messages = ref<Message[]>([])
const userInput = ref('')
const isGenerating = ref(false)
const messagesContainer = ref<HTMLElement>()

// 找到最新的带 codeGen 的 AI 消息，用于下半部分独立代码面板展示
const latestCodeGen = computed(() => {
  const msgs = messages.value
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].type === 'ai' && msgs[i].codeGen) {
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
            // AI 消息尝试解析代码生成结果 JSON
            if (base.type === 'ai' && chat.message) {
              const stripped = stripMarkdownCodeFence(chat.message)
              const parsed = tryParseCodeGenResult(stripped)
              if (parsed) {
                base.content = parsed.description || ''
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
function getLanguageByFileName(fileName: string): string {
  const ext = fileName.split('_').pop() || ''
  const langMap: Record<string, string> = {
    html: 'html',
    css: 'css',
    js: 'javascript',
    vue: 'html',
    react: 'jsx',
    python: 'python',
    ts: 'typescript',
    json: 'json',
    md: 'markdown',
  }
  return langMap[ext] || 'plaintext'
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
    let firstFileName: string | null = null
    let firstFileDone = false

    const finalizeGeneration = () => {
      streamCompleted = true
      isGenerating.value = false
      // 剥离 markdown 代码块包裹后再解析
      const cleaned = stripMarkdownCodeFence(rawContentBuffer)
      const result = tryParseCodeGenResult(cleaned)
      if (result) {
        aiMessage.codeGen = result
      }
      aiMessage.loading = false
      setTimeout(async () => {
        await fetchAppInfo()
        updatePreview()
      }, 1000)
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

        if (eventType === 'business-error') {
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

        // message 事件：累积 token（后端字段名为 "d"）
        try {
          const parsed = JSON.parse(dataStr)
          if (parsed.d !== undefined && parsed.d !== null) {
            rawContentBuffer += parsed.d
          }
        } catch {
          rawContentBuffer += dataStr
        }

        // 尝试完整解析（先剥离 markdown 代码块包裹）
        const fullResult = tryParseCodeGenResult(stripMarkdownCodeFence(rawContentBuffer))
        if (fullResult) {
          aiMessage.codeGen = fullResult
          aiMessage.loading = false
          firstFileDone = true
          scrollToBottom()
          continue
        }

        // 尝试提取 app_name / description
        if (!aiMessage.codeGen) {
          const appName = extractSimpleField(rawContentBuffer, 'app_name')
          const description = extractSimpleField(rawContentBuffer, 'description')
          if (appName || description) {
            aiMessage.codeGen = {
              app_name: appName || '',
              description: description || '',
              files: [],
              currentFileIndex: 0,
              isComplete: false,
            }
          }
        } else {
          if (!aiMessage.codeGen.app_name) {
            const v = extractSimpleField(rawContentBuffer, 'app_name')
            if (v) aiMessage.codeGen.app_name = v
          }
          if (!aiMessage.codeGen.description) {
            const v = extractSimpleField(rawContentBuffer, 'description')
            if (v) aiMessage.codeGen.description = v
          }
        }

        // 第一个代码文件的实时流式显示
        if (!firstFileDone) {
          if (!firstFileName) firstFileName = findFirstCodeField(rawContentBuffer)
          if (firstFileName) {
            const partial = extractPartialField(rawContentBuffer, firstFileName)
            if (partial !== null) {
              const display = unescapeJson(partial)
              if (aiMessage.codeGen) {
                const existing = aiMessage.codeGen.files.find((f) => f.name === firstFileName)
                if (existing) existing.content = display
                else {
                  aiMessage.codeGen.files.push({
                    name: firstFileName,
                    label: CODE_FIELD_MAP[firstFileName] || firstFileName,
                    content: display,
                  })
                }
                aiMessage.loading = false
                scrollToBottom()
              }
            }
            if (isFieldComplete(rawContentBuffer, firstFileName)) firstFileDone = true
          }
        }
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
  flex: 2;
  min-height: 0;
  padding: 8px 16px 16px;
  border-top: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.code-viewer-panel .codeGen-viewer {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
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
