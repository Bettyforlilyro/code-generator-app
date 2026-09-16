/**
 * 环境变量配置
 */
import { CodeGenTypeEnum } from '@/utils/codeGenTypes.ts'

// 应用部署域名
export const DEPLOY_DOMAIN = import.meta.env.VITE_DEPLOY_DOMAIN || 'http://localhost'

// API 基础地址 — 使用相对路径,这样 iframe src 也走同域,Vite 代理转发到后端
// 开发环境: VITE_API_BASE_URL=/api → /api/v1/... (Vite 代理到后端)
// 生产环境: VITE_API_BASE_URL=/api → /api/v1/... (Nginx 同域部署)
export const API_BASE_URL = `${import.meta.env.VITE_API_BASE_URL || '/api'}/v1`

// 获取静态资源预览URL
export const getStaticPreviewUrl = (codeGenType: string, appId: string) => {
  const baseUrl = `${API_BASE_URL}/code/static/${codeGenType}_${appId}/`
  // 如果是 Vue 项目，浏览地址需要添加 dist 后缀
  if (codeGenType === CodeGenTypeEnum.VUE_PROJECT) {
    return `${baseUrl}dist/index.html`
  }
  return baseUrl
}

// 获取部署应用的完整URL
export const getDeployUrl = (deployKey: string) => {
  return `${DEPLOY_DOMAIN}/${deployKey}`
}

// 获取静态资源列表接口URL（用于获取文件列表信息）
export const getStaticListUrl = (codeGenType: string, appId: string) => {
  return `${API_BASE_URL}/code/static/${codeGenType}_${appId}`
}

// 获取已部署应用的静态资源列表接口URL
export const getDeployedStaticListUrl = (deployKey: string) => {
  return `${API_BASE_URL}/code/static?deploy_key=${deployKey}`
}

// 从文件列表中解析预览URL（查找 index.html）
export const resolvePreviewUrlFromList = (files: Array<{ file_name: string; file_url: string }>): string | null => {
  const indexFile = files.find((f) => f.file_name === 'index.html')
  if (!indexFile) return null
  // 将相对路径转为完整 URL
  if (indexFile.file_url.startsWith('http')) return indexFile.file_url
  // 相对路径用当前域名(同域),Vite 代理或 Nginx 转发到后端
  return `${indexFile.file_url}`
}
