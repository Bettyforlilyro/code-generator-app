import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getLoginUser } from '@/api/userController.ts'

const TOKEN_KEY = 'token'

/**
 * 登录用户信息
 */
export const useLoginUserStore = defineStore('loginUser', () => {
  // 默认值
  const loginUser = ref<API.LoginUserVO>({
    user_name: '未登录',
  })

  // 获取本地 token
  function getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY)
  }

  // 保存token
  function setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token)
  }

  // 清除token
  function clearToken(): void {
    localStorage.removeItem(TOKEN_KEY)
  }


  // 获取登录用户信息
  async function fetchLoginUser() {
    const res = await getLoginUser()
    if (res.data.code === 20000 && res.data.data) {
      loginUser.value = res.data.data
    }
  }

  // 更新登录用户信息
  function setLoginUser(newLoginUser: any) {
    loginUser.value = newLoginUser
  }

  // 登出（清除token + 清空用户信息）
  function logout() {
    clearToken()
    loginUser.value = {
      user_name: '未登录',
    }
  }

  return { loginUser, fetchLoginUser, setLoginUser, logout, getToken, setToken, clearToken }
})
