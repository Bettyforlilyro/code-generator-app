from backend.app.api.v1.user_management import user_management_bp
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.common.utils.request_helpers import parse_json_body
from backend.app.schemas.requests.user_management_request import UserRegisterRequest
from backend.app.schemas.responses.BaseResponse import success_response
from backend.app.services.auth_service import register_user_svc


@user_management_bp.route('/register', methods=['POST'])
def register():
    """
    用户注册接口
    ---
    tags:
      - 用户管理
    summary: 用户注册
    description: 创建新用户账号并返回用户信息，密码需满足复杂度要求
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - user_name
            - user_password
            - confirm_password
          properties:
            user_name:
              type: string
              maxLength: 256
              description: 用户昵称
              example: 张三
            user_password:
              type: string
              maxLength: 512
              description: 用户密码（至少6位，包含大写/小写/数字/特殊符号中的两种）
              example: Password123!
            confirm_password:
              type: string
              maxLength: 512
              description: 确认密码
              example: Password123!
    responses:
      200:
        description: ✅ 响应示例1：注册成功 - 返回用户基本信息
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 20000
            message:
              type: string
              example: 操作成功
            data:
              type: object
              properties:
                id:
                  type: integer
                  example: 1
                user_account:
                  type: string
                  example: user_123456abcd
                user_name:
                  type: string
                  example: 张三
                user_role:
                  type: string
                  example: user
                access_token:
                  type: string
                  description: 短期访问令牌（15分钟有效）
                  example: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
      400:
        description: ❌ 响应示例2：请求参数错误 - 用户名或密码无效
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 40003
            message:
              type: string
              example: 密码复杂度过低，请至少包含大写或小写字母、数字、特殊符号中的其中两种
            data:
              type: object
              nullable: true
              example: null
      500:
        description: 💥 响应示例3：服务器内部错误 - 请联系管理员
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 50000
            message:
              type: string
              example: 服务器内部错误
    """
    json_data = parse_json_body()
    user_name = json_data.get('user_name')
    pass_word = json_data.get('user_password')
    confirm_password = json_data.get('confirm_password')
    if not user_name or not pass_word or not confirm_password:
        raise BusinessException(ErrorCode.INVALID_PARAMETER, "用户名和密码不能为空")

    req = UserRegisterRequest(**json_data)
    register_response = register_user_svc(req)

    return success_response(register_response.model_dump())