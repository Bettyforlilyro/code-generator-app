// @ts-ignore
/* eslint-disable */
import request from '@/request'

/** 此处后端没有提供注释 GET /app/${app_id}/chat_history */
export async function listAllChatHistoryByPageForAdmin(
  body: API.ChatHistoryQueryRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponsePageChatHistory>(`/app/${body.app_id}/chat_history`, {
    method: 'GET',
    params: {
      'Content-Type': 'application/json',
      ...body,
    },
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/${app_id}/chat_history */
export async function listAppChatHistory(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.listAppChatHistoryParams,
  options?: { [key: string]: any }
) {
  const { app_id: param0, ...queryParams } = params
  return request<API.BaseResponsePageChatHistory>(`/app/${param0}/chat_history`, {
    method: 'GET',
    params: {
      // per_page has a default value: 10
      per_page: '10',
      ...queryParams,
    },
    ...(options || {}),
  })
}
