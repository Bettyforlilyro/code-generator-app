/**
 * 环境变量配置
 */
import { CodeGenTypeEnum } from '@/utils/codeGenTypes.ts'

// 应用部署域名
export const DEPLOY_DOMAIN = import.meta.env.VITE_DEPLOY_DOMAIN || 'http://localhost'

// API 基础地址
export const API_BASE_URL = 'http://localhost:5000/api/v1'

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
export const resolvePreviewUrlFromList = (files: Array<{ file_url: string }>): string | null => {
  const indexFile = files.find((f) => f.file_name === 'index.html')
  if (!indexFile) return null
  // TODO 调试待删除
  console.log("indexFile: ", indexFile)
  // 将相对路径转为绝对路径
  if (indexFile.file_url.startsWith('http')) return indexFile.file_url
  return `http://localhost:5000${indexFile.file_url}`
}
