import axios from 'axios'
import { message } from 'ant-design-vue'
import { API_BASE_URL } from '@/config/env'

const TOKEN_KEY = 'token'

// 是否正在刷新token的表示（防止并发请求重复出发刷新
let isRefresh = false
// 是否在跳转登录页（防止多次redirect）
let isRedirecting = false
// 等待刷新完成的请求队列，刷新完成后重发发送这些请求
let pendingRequests: Array<{
  config: any
  resolve: (value: any) => void
  reject: (reason?: any) => void
}> = []

// 创建 Axios 实例
const myAxios = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  withCredentials: true,
})

// 用refresh_token换取新的access_token，使用独立的axios请求（不走myAxios拦截器，避免循环出发401未登录）
async function refreshAccessToken(): Promise<string> {
  const res = await axios.post(
    `${API_BASE_URL}/user/refresh`,
    {},
    {
      withCredentials: true, // 自动携带Cookie中的refresh_token，必须true
      headers: {
        'Content-Type': 'application/json',
      },
    },
  )
  if (res.data.code === 20000 && res.data.data && res.data.data.token) {
    localStorage.setItem(TOKEN_KEY, res.data.data.token)
    return res.data.data.token
  }
  throw new Error('刷新access_token失败，refresh_token也过期了，请重新登录')
}

// 通知等待队列中的所有请求：刷新成功则重试，失败则 reject
function resolvePendingRequests(newToken: string | null, error?: Error) {
  pendingRequests.forEach((item) => {
    if (error) {
      item.reject(error)
    } else {
      if (!item.config.headers) {
        item.config.headers = {}
      }
      item.config.headers.Authorization = `Bearer ${newToken}`
      // 重新发起请求（走 myAxios 拦截器）
      item.resolve(myAxios.request(item.config))
    }
  })
  pendingRequests = []
}

// 全局请求拦截器
myAxios.interceptors.request.use(
  function (config) {
    // 从localStorage 读取token，并添加到 Authorization请求头
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  function (error) {
    // Do something with request error
    return Promise.reject(error)
  },
)

// 全局响应拦截器
myAxios.interceptors.response.use(
  // 成功响应拦截器，当前仅在登录成功时保存token
  async function (response) {
    const { data } = response
    // 登录成功时保存access_token
    if (data.code === 20000 && data.data && data.data.token) {
      localStorage.setItem(TOKEN_KEY, data.data.token)
    }
    return response
  },
  // 错误响应拦截器（HTTP 非 2xx，所有的认证错误统一在这里处理）
  async function (error) {
    if (error.response) {
      const { status, data } = error.response
      const config = error.config
      // 登录页面返回的401 + 40100，说明登录失败，需要直接返回，不拦截了以便界面提示错误
      if (status === 401 && data.code === 40100 && config.url?.includes('user/login')) {
        return error.response
      }
      // refresh token 返回的40100，说明登录过期，需要跳转登录页
      if (status === 401 && data.code === 40100 && config.url?.includes('user/refresh')) {
        localStorage.removeItem(TOKEN_KEY)
        if (!isRedirecting) {
          isRedirecting = true
          message.warning('登录已过期，请重新登录！')
          window.location.href = `/user/login?redirect=${window.location.href}`
        }
        return Promise.reject(error)
      }
      // 其他接口返回的401：说明access token过期，需要使用refresh token刷新新的access token
      if (status === 401 && data.code === 40100) {
        // 正在刷新中，当前请求进入排队队列等待
        if (isRefresh) {
          return new Promise((resolve, reject) => {
            pendingRequests.push({ config, resolve, reject })
          })
        }
        // 开始刷新 token
        isRefresh = true
        try {
          const newToken = await refreshAccessToken()
          isRefresh = false
          // 通知队列中的请求用新token重试
          resolvePendingRequests(newToken)
          // 用新token重试当前请求
          if (!config.headers) {
            config.headers = {}
          }
          config.headers.Authorization = `Bearer ${newToken}`
          return myAxios.request(config)
        } catch (err) {
          // 刷新失败，说明refresh token也过期了，需要跳转登录页
          isRefresh = false
          resolvePendingRequests(null, err as Error)
          localStorage.removeItem(TOKEN_KEY)
          if (!isRedirecting) {
            isRedirecting = true
            message.warning('登录已过期，请重新登录！')
            window.location.href = `/user/login?redirect=${window.location.href}`
          }
          return Promise.reject(err)
        }
      }
      // 注册接口返回的失败，需要返回给用户原因提示
      return error.response
    }
    return Promise.reject(error)
  },
)

export default myAxios
