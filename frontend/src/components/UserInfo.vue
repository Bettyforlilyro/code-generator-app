<template>
  <div class="user-info">
    <a-avatar :src="displayAvatar" :size="size">
      {{ displayName?.charAt(0) || 'U' }}
    </a-avatar>
    <span v-if="showName" class="user-name">{{ displayName || '未知用户' }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  /** 用户对象（完整形式，兼容旧用法） */
  user?: API.UserVO
  /** 用户名（扁平形式，优先使用） */
  userName?: string
  /** 用户头像（扁平形式，优先使用） */
  userAvatar?: string
  /** 头像大小 */
  size?: number | 'small' | 'default' | 'large'
  /** 是否显示用户名 */
  showName?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 'default',
  showName: true,
})

// 计算最终显示的用户名：优先用扁平 prop，其次从 user 对象取
const displayName = computed(() => {
  if (props.userName !== undefined) return props.userName
  return props.user?.user_name ?? props.user?.user_name ?? ''
})

// 计算最终显示的头像：优先用扁平 prop，其次从 user 对象取
const displayAvatar = computed(() => {
  const raw = props.userAvatar !== undefined ? props.userAvatar : (props.user?.user_avatar ?? '')
  if (!raw) return ''
  try {
    return encodeURI(raw)
  } catch {
    return raw
  }
})
</script>

<style scoped>
.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-name {
  font-size: 14px;
  color: #1a1a1a;
}
</style>
