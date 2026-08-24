declare namespace API {
  type AppAddRequest = {
    init_prompt?: string
  }

  type AppAdminUpdateRequest = {
    id?: number
    app_name?: string
    cover?: string
    priority?: number
  }

  type AppDeployRequest = {
    app_id?: number
  }

  type AppQueryRequest = {
    page?: number
    per_page?: number
    sort_field?: string
    sort_order?: string
    id?: number
    app_name?: string
    cover?: string
    init_prompt?: string
    code_gen_type?: string
    deploy_key?: string
    priority?: number
    user_id?: number
  }

  type AppUpdateRequest = {
    id?: number
    app_name?: string
  }

  type AppVO = {
    id?: number
    app_name?: string
    cover?: string
    init_prompt?: string
    code_gen_type?: string
    deploy_key?: string
    deployed_time?: string
    priority?: number
    user_id?: number
    create_time?: string
    update_time?: string
    user?: UserVO
  }

  type BaseResponseAppVO = {
    code?: number
    data?: AppVO
    message?: string
  }

  type BaseResponseBoolean = {
    code?: number
    data?: boolean
    message?: string
  }

  type BaseResponseLoginUserVO = {
    code?: number
    data?: LoginUserVO
    message?: string
  }

  type BaseResponseLong = {
    code?: number
    data?: number
    message?: string
  }

  type BaseResponsePageAppVO = {
    code?: number
    data?: PageAppVO
    message?: string
  }

  type BaseResponsePageChatHistory = {
    code?: number
    data?: PageChatHistory
    message?: string
  }

  type BaseResponsePageUserVO = {
    code?: number
    data?: PageUserVO
    message?: string
  }

  type BaseResponseString = {
    code?: number
    data?: string
    message?: string
  }

  type BaseResponseUser = {
    code?: number
    data?: User
    message?: string
  }

  type BaseResponseUserVO = {
    code?: number
    data?: UserVO
    message?: string
  }

  type ChatHistory = {
    id?: number
    message?: string
    message_type?: string
    app_id?: number
    user_id?: number
    create_time?: string
    update_time?: string
    is_delete?: number
  }

  type ChatHistoryQueryRequest = {
    page?: number
    per_page?: number
    sort_field?: string
    sort_order?: string
    id?: number
    message?: string
    message_type?: string
    app_id?: number
    user_id?: number
    last_create_time?: string
  }

  type chatToGenCodeParams = {
    app_id: number
    message: string
  }

  type DeleteRequest = {
    id?: number
  }

  type downloadAppCodeParams = {
    app_id: number
  }

  type getAppVOByIdByAdminParams = {
    id: number
  }

  type getAppVOByIdParams = {
    id: number
  }

  type getUserByIdParams = {
    id: number
  }

  type getUserVOByIdParams = {
    id: number
  }

  type listAppChatHistoryParams = {
    app_id: number
    per_page?: number
    last_create_time?: string
  }

  type LoginUserVO = {
    id?: number
    user_account?: string
    user_name?: string
    user_avatar?: string
    user_profile?: string
    user_role?: string
    create_time?: string
    update_time?: string
    token?: string
  }

  type PageAppVO = {
    records?: AppVO[]
    page?: number
    per_page?: number
    total_page?: number
    total_row?: number
    optimize_count_query?: boolean
  }

  type PageChatHistory = {
    records?: ChatHistory[]
    page?: number
    per_page?: number
    total_page?: number
    total_row?: number
    optimize_count_query?: boolean
  }

  type PageUserVO = {
    users?: UserVO[]
    page?: number
    per_page?: number
    total_page?: number
    total?: number
    optimize_count_query?: boolean
  }

  type ServerSentEventString = true

  type serveStaticResourceParams = {
    deploy_key: string
  }

  type User = {
    id?: number
    user_account?: string
    user_password?: string
    user_name?: string
    user_avatar?: string
    user_profile?: string
    user_role?: string
    edit_time?: string
    create_time?: string
    update_time?: string
    is_delete?: number
  }

  type UserAddRequest = {
    user_name?: string
    user_password?: string
    confirm_password?: string
    user_role?: string
  }

  type UserLoginRequest = {
    user_name?: string
    user_password?: string
  }

  type UserQueryRequest = {
    page?: number
    per_page?: number
    sort_field?: string
    sort_order?: string
    id?: number
    user_name?: string
    user_account?: string
    user_profile?: string
    user_role?: string
  }

  type UserRegisterRequest = {
    user_name?: string
    user_password?: string
    confirm_password?: string
  }

  type UserUpdateRequest = {
    id?: number
    user_name?: string
    user_avatar?: string
    user_profile?: string
    user_role?: string
  }

  type UserVO = {
    id?: number
    user_account?: string
    user_name?: string
    user_avatar?: string
    user_profile?: string
    user_role?: string
    create_time?: string
  }
}
