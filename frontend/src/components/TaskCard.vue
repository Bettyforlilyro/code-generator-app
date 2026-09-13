<template>
  <!-- 阶段1: running / done 闪烁阶段 -->
  <div
    v-if="phase !== 'collapsed'"
    class="task-card"
    :class="{ 'task-done': phase === 'done', 'task-collapsing': phase === 'collapsing' }"
  >
    <!-- 状态图标 -->
    <div class="task-icon">
      <a-spin v-if="phase === 'running'" size="small" />
      <CheckCircleOutlined v-else class="task-done-icon" />
    </div>

    <!-- 任务类型标签 -->
    <span class="task-label">{{ getTaskLabel(task.type) }}</span>

    <!-- 任务 info 说明 -->
    <div class="task-info-wrapper">
      <div v-if="task.info" class="task-info">
        <MarkdownRenderer :content="task.info" />
      </div>
      <div v-else-if="task.status === 'running'" class="task-info running-placeholder">
        任务执行中...
      </div>

      <!-- 文件预览按钮(hasPreview 由父组件传入) -->
      <a-tooltip v-if="hasPreview" :title="previewActive ? '关闭预览' : '预览文件'" placement="top">
        <component
          :is="previewActive ? EyeInvisibleOutlined : EyeOutlined"
          class="preview-icon"
          :class="{ active: previewActive }"
          @click="togglePreview"
        />
      </a-tooltip>
    </div>
  </div>

  <!-- 阶段2: 任务彻底完成后,只保留 info 文本(纯 Markdown,无框无图标) -->
  <div v-else-if="task.info" class="task-info-collapsed">
    <MarkdownRenderer :content="task.info" />
    <!-- 即使 collapsed 了,预览按钮也保留在 info 右上角(如果可预览) -->
    <a-tooltip v-if="hasPreview" :title="previewActive ? '关闭预览' : '预览文件'" placement="top">
      <component
        :is="previewActive ? EyeInvisibleOutlined : EyeOutlined"
        class="preview-icon inline"
        :class="{ active: previewActive }"
        @click="togglePreview"
      />
    </a-tooltip>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import type { TaskItem } from '@/pages/app/AppChatPage.vue'
import { CheckCircleOutlined, EyeInvisibleOutlined, EyeOutlined } from '@ant-design/icons-vue'

const props = defineProps<{
  task: TaskItem
  // 可选:当前是否正在被预览(由父组件传入,支持多个 TaskCard 互斥预览)
  previewActive?: boolean
  // 是否有可预览文件(父组件从 extra 里算好再传进来,绕开子组件 computed 响应式追踪边界)
  hasPreview?: boolean
}>()

const emit = defineEmits<{
  (e: 'preview', task: TaskItem): void
  (e: 'close-preview'): void
}>()

// 动画阶段: running → done(闪烁) → collapsing(淡出) → collapsed(只留 info)
// 注意: phase 是内部视觉状态,与 task.status 不完全同步
type Phase = 'running' | 'done' | 'collapsing' | 'collapsed'
const phase = ref<Phase>(props.task.status === 'done' ? 'collapsed' : 'running')
let collapseTimer: ReturnType<typeof setTimeout> | null = null

// 监视 task.status 变化,触发完成动画
watch(
  () => props.task.status,
  (newStatus, oldStatus) => {
    if (newStatus === 'done' && oldStatus === 'running') {
      // running → done: 先闪一下绿色 ✓,然后自动折叠
      phase.value = 'done'
      clearTimers()
      collapseTimer = setTimeout(() => {
        phase.value = 'collapsing'
        collapseTimer = setTimeout(() => {
          phase.value = 'collapsed'
        }, 300) // collapsing 过渡时长
      }, 800) // done 状态保持时长
    } else if (newStatus === 'done' && oldStatus !== 'done') {
      // 初始就是 done(历史消息回显):直接 collapsed
      phase.value = 'collapsed'
    } else if (newStatus === 'running') {
      phase.value = 'running'
      clearTimers()
    }
  },
  { immediate: true },
)

function clearTimers() {
  if (collapseTimer) {
    clearTimeout(collapseTimer)
    collapseTimer = null
  }
}

onBeforeUnmount(clearTimers)

// 点击预览按钮:切换预览状态
function togglePreview() {
  if (props.previewActive) {
    emit('close-preview')
  } else {
    emit('preview', props.task)
  }
}

// 任务类型 → 显示标签
function getTaskLabel(type: string): string {
  const map: Record<string, string> = {
    tool_call: '工具调用',
    web_search: '网络搜索',
    file_write: '文件写入',
    file_edit: '文件修改',
  }
  return map[type] || type
}
</script>

<style scoped>
.task-card {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f6f8fa;
  border: 1px solid #e4e7eb;
  font-size: 14px;
  line-height: 1.5;
  margin: 8px 0;
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    opacity 0.3s ease;
}

.task-card.task-done {
  background: #f0f9eb;
  border-color: #e1f3d8;
}

.task-card.task-collapsing {
  opacity: 0;
  transform: translateY(-4px);
}

.task-icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}

.task-done-icon {
  color: #52c41a;
  font-size: 18px;
}

.task-label {
  flex-shrink: 0;
  font-weight: 600;
  color: #606266;
  padding: 2px 8px;
  background: #e9ebf0;
  border-radius: 4px;
  font-size: 12px;
}

.task-card.task-done .task-label {
  color: #67c23a;
  background: #e1f3d8;
}

.task-info-wrapper {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.task-info {
  flex: 1;
  min-width: 0;
  color: #606266;
}

.task-info :deep(.markdown-content) {
  font-size: 13px;
  line-height: 1.5;
  color: #606266;
}

.task-info :deep(.markdown-content p) {
  margin: 0.2em 0;
}

.running-placeholder {
  color: #909399;
  font-style: italic;
}

/* 折叠后:只保留 info 文本(纯 Markdown 样式,与普通文本融为一体) */
.task-info-collapsed {
  position: relative;
  margin: 4px 0;
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
}

.task-info-collapsed :deep(.markdown-content) {
  font-size: 14px;
  line-height: 1.6;
  color: #606266;
}

.task-info-collapsed :deep(.markdown-content p) {
  margin: 0.4em 0;
}

/* 预览图标 */
.preview-icon {
  flex-shrink: 0;
  font-size: 16px;
  color: #1890ff;
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  transition:
    color 0.2s,
    background 0.2s;
}

.preview-icon:hover {
  color: #40a9ff;
  background: #e6f7ff;
}

.preview-icon.active {
  color: #ffffff;
  background: #1890ff;
}

.preview-icon.inline {
  position: absolute;
  top: 0;
  right: 0;
  font-size: 14px;
  padding: 1px 4px;
}
</style>
