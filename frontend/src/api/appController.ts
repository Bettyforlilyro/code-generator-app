// @ts-ignore
/* eslint-disable */
import request from '@/request'

/** 此处后端没有提供注释 POST /app */
export async function addApp(body: API.AppAddRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseAppVO>('/app', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 PUT /app/${app_id} */
export async function updateAppByAdmin(
  body: API.AppAdminUpdateRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseBoolean>(`/app/${body.id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 PUT /app/${app_id} */
export async function updateApp(body: API.AppUpdateRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>(`/app/${body.id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 DELETE /app/${app_id} */
export async function deleteApp(body: API.DeleteRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>(`/app/${body.id}`, {
    method: 'DELETE',
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 DELETE /app/${app_id} */
export async function deleteAppByAdmin(body: API.DeleteRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>(`/app/${body.id}`, {
    method: 'DELETE',
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/{app_id} */
export async function getAppVoById(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getAppVOByIdParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseAppVO>(`/app/${params.id}`, {
    method: 'GET',
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/good/list/page/vo */
export async function listGoodAppVoByPage(
  body: API.AppQueryRequest,
  options?: { [key: string]: any }
) {
  // 过滤掉空值参数，只传递有值的参数
  const params: Record<string, any> = {}
  if (body.page !== undefined) params.page = body.page
  if (body.per_page !== undefined) params.per_page = body.per_page

  return request<API.BaseResponsePageAppVO>('/app/good/list', {
    method: 'GET',
    params: params,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/list */
export async function listAppVoByPageByAdmin(
  body: API.AppQueryRequest,
  options?: { [key: string]: any }
) {
  // 过滤掉空值参数，只传递有值的参数
  const params: Record<string, any> = {}
  if (body.page !== undefined) params.page = body.page
  if (body.per_page !== undefined) params.per_page = body.per_page
  if (body.user_name !== undefined) params.user_name = body.user_name
  if (body.app_name !== undefined) params.app_name = body.app_name
  if (body.code_gen_type !== undefined) params.code_gen_type = body.code_gen_type
  if (body.sort_field !== undefined) params.sort_field = body.sort_field
  if (body.sort_order !== undefined) params.sort_order = body.sort_order

  return request<API.BaseResponsePageAppVO>('/app/list', {
    method: 'GET',
    params: params,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/list */
export async function listMyAppVoByPage(
  body: API.AppQueryRequest,
  options?: { [key: string]: any }
) {
  // 过滤掉空值参数，只传递有值的参数
  const params: Record<string, any> = {}
  params.is_mine = true
  if (body.page !== undefined) params.page = body.page
  if (body.per_page !== undefined) params.per_page = body.per_page
  if (body.code_gen_type !== undefined) params.code_gen_type = body.code_gen_type
  if (body.app_name !== undefined) params.app_name = body.app_name
  if (body.sort_field !== undefined) params.sort_field = body.sort_field
  if (body.sort_order !== undefined) params.sort_order = body.sort_order

  return request<API.BaseResponsePageAppVO>('/app/list', {
    method: 'GET',
    params: params,
    ...(options || {}),
  })
}


/** 此处后端没有提供注释 POST /app/deploy */
export async function deployApp(body: API.AppDeployRequest, options?: { [key: string]: any }) {
  return request<API.AppDeployResponse>('/app/deploy', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/download/${param0} */
export async function downloadAppCode(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.downloadAppCodeParams,
  options?: { [key: string]: any }
) {
  const { app_id: param0, ...queryParams } = params
  return request<any>(`/app/download/${param0}`, {
    method: 'GET',
    params: { ...queryParams },
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/chat/gen/code */
export async function chatToGenCode(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.chatToGenCodeParams,
  options?: { [key: string]: any }
) {
  return request<API.ServerSentEventString[]>('/app/chat/gen/code', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}
