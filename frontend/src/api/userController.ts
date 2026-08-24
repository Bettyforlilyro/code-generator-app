// @ts-ignore
/* eslint-disable */
import request from '@/request'

/** 管理员直接新增用户 POST /user */
export async function addUser(body: API.UserAddRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseLong>('/user', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 管理员直接删除用户 DELETE /user */
export async function deleteUser(body: API.DeleteRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>(`/user/${body.id}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /user/login */
export async function getLoginUser(options?: { [key: string]: any }) {
  return request<API.BaseResponseLoginUserVO>('/user/login', {
    method: 'GET',
    ...(options || {}),
  })
}

  /** 用户分页列表VO接口 GET /user */
export async function listUserVoByPage(
  body: API.UserQueryRequest,
  options?: { [key: string]: any }
) {
  // 过滤掉空值参数，只传递有值的参数
  const params: Record<string, any> = {}
  if (body.page !== undefined) params.page = body.page
  if (body.per_page !== undefined) params.per_page = body.per_page
  if (body.user_account) params.user_account = body.user_account
  if (body.user_name) params.user_name = body.user_name
  if (body.user_role) params.user_role = body.user_role
  if (body.sort_field) params.sort_field = body.sort_field
  if (body.sort_order) params.sort_order = body.sort_order

  return request<API.BaseResponsePageUserVO>('/user', {
    method: 'GET',
    params: {
      ...params,
      ...(options || {}),
    },
  })
}

/** 此处后端没有提供注释 POST /user/login */
export async function userLogin(body: API.UserLoginRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseLoginUserVO>('/user/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /user/logout */
export async function userLogout(options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/user/logout', {
    method: 'POST',
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /user/register */
export async function userRegister(
  body: API.UserRegisterRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseLong>('/user/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 管理员直接更新用户 PUT /user */
export async function updateUser(body: API.UserUpdateRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>(`/user/${body.id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}
