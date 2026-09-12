<template>
  <div class="task-card" :class="{ 'task-done': task.status === 'done' }">
    <!-- 状态图标 -->
    <div class="task-icon">
      <a-spin v-if="task.status === 'running'" size="small" />
      <a-icon v-else type="check-circle" class="task-done-icon" />
    </div>

    <!-- 任务类型标签 -->
    <span class="task-label">{{ getTaskLabel(task.type) }}</span>

    <!-- 任务 info 说明 -->
    <div v-if="task.info" class="task-info">
      <MarkdownRenderer :content="task.info" />
    </div>
    <div v-else-if="task.status === 'running'" class="task-info running-placeholder">
      任务执行中...
    </div>
  </div>
</template>

<script setup lang="ts">
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import type { TaskItem } from '@/pages/app/AppChatPage.vue'

defineProps<{
  task: TaskItem
}>()

// 任务类型 → 显示标签
function getTaskLabel(type: string): string {
  const map: Record<string, string> = {
    tool_call: '工具调用',
    web_search: '网络搜索',
    file_write: '文件写入',
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
  transition: background 0.2s ease, border-color 0.2s ease;
}

.task-card.task-done {
  background: #f0f9eb;
  border-color: #e1f3d8;
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
</style>
