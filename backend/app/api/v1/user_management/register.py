import asyncio
import time
import uuid

from flask import request, after_this_request, current_app

from backend.app.api.v1.user_management import user_management_bp
from backend.app.common.emuns.user_role import UserRole
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.common.utils.get_random_avatar import get_random_avatar
from backend.app.models.user import User
from backend.app.common.utils.auth import generate_access_token, generate_refresh_token
from backend.app.extensions.db_instance import db
from backend.app.schemas.requests.user_management_request import UserRegisterRequest
from backend.app.schemas.responses.BaseResponse import success_response, error_response, stream_response
from backend.app.schemas.responses.user_management_response import UserRegisterResponse


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
    try:
        # 1. 获取并验证请求数据
        json_data = request.get_json()
        if not json_data:
            return error_response(ErrorCode.BAD_REQUEST, "请求体不能为空")
        user_name = json_data.get('user_name')
        pass_word = json_data.get('user_password')
        confirm_password = json_data.get('confirm_password')
        if not user_name or not pass_word or not confirm_password:
            return error_response(ErrorCode.INVALID_PARAMETER, "用户名和密码不能为空")

        # 使用Pydantic验证请求数据，里面已经实现了密码复杂度检查和确认密码检查
        req = UserRegisterRequest(**json_data)

        # 2. 生成唯一的用户账号
        user_account = generate_user_account(req.user_name)

        # 3. 检查账号是否已存在（理论上不会重复，但为了安全还是检查一下）
        existing_user = User.query.filter_by(user_name=req.user_name, is_delete=0).first()
        if existing_user:
            return error_response(ErrorCode.INVALID_PARAMETER, "用户名已存在")

        # 随机调用API获取一个用户头像
        user_avatar = get_random_avatar()

        # 4. 创建新用户
        new_user = User(
            user_account=user_account,
            user_name=req.user_name,
            user_avatar=user_avatar,
            user_role=UserRole.USER.value
        )

        # 5. 设置加密密码
        new_user.set_password(req.user_password)

        # 6. 保存到数据库
        db.session.add(new_user)
        db.session.commit()

        # 7. 注册后自动以当前用户登录，生成双Token
        access_token = generate_access_token(new_user.id, new_user.user_role)
        ref_token = generate_refresh_token(new_user.id)

        def set_refresh_cookie(resp):
            is_debug = current_app.config.get('DEBUG', False)
            resp.set_cookie(
                'refresh_token',
                ref_token,
                httponly=True,
                secure=not is_debug,    # is_debug 开发环境使用 False，生产环境使用 True
                samesite='Lax',
                max_age=7 * 24 * 60 * 60,
                path='/api/v1/user/refresh'
            )
            return resp
        # 注册回调函数设置Cookie返回给前端，主要是为了保存 Refresh Token
        after_this_request(set_refresh_cookie)

        # 8. 创建包含 Access Token 的响应
        response_data = UserRegisterResponse(
            id=new_user.id,
            user_account=new_user.user_account,
            user_name=new_user.user_name,
            user_role=new_user.user_role,
            token=access_token
        )

        return success_response(response_data.model_dump())

    except BusinessException as e:
        db.session.rollback()
        return error_response(e.error_code, e.message, e.data)

    except Exception as e:
        db.session.rollback()
        return error_response(ErrorCode.INTERNAL_ERROR, f"注册失败: {str(e)}")


def generate_user_account(user_name: str) -> str:
    """
    生成唯一的用户账号

    规则：user_ + 时间戳后6位 + 随机4位字符

    Args:
        user_name: 用户昵称（可用于调试日志，但不直接用于账号生成）

    Returns:
        唯一的用户账号字符串
    """
    # 使用时间戳后6位 + UUID的前4位作为唯一标识
    timestamp_suffix = str(int(time.time() * 1000))[-6:]
    random_suffix = str(uuid.uuid4()).replace('-', '')[:4]

    user_account = f"user_{timestamp_suffix}{random_suffix}"

    return user_account


# TODO 待删除
@user_management_bp.route('/generate_code', methods=['GET'])
def generate_code():

    def token_generator():
        # 模拟 AI 流式输出
        for token in ['你', '好', '，', '世', '界']:
            yield {'token': token}

    # 使用 after_this_request 设置额外响应头（如用户所述）
    @after_this_request
    def add_headers(response):
        response.headers['X-Custom-Header'] = 'value'
        return response

    # 使用 stream_response 包装
    return stream_response(
        generator=token_generator(),
        event_type='token',
        use_wrapper=True  # 每个数据块会被包装为 ApiResponse 格式
    )


@user_management_bp.route('/api/raw-stream', methods=['GET'])
def raw_stream():
    def raw_generator():
        yield "原始文本数据1"
        yield "原始文本数据2"
        yield {"key": "value"}  # 也可以是 dict，会自动序列化

    return stream_response(
        generator=raw_generator(),
        event_type='raw',
        use_wrapper=False  # 不包装，直接输出
    )


@user_management_bp.route('/api/generate-with-callbacks', methods=['POST'])
def generate_with_callbacks():
    def token_generator():
        yield {'step': 1, 'content': '第一步'}
        yield {'step': 2, 'content': '第二步'}
        # 如果发生异常，会触发 on_error

    def on_done_callback():
        # 流结束时发送的最后一条消息
        return {"final_result": "所有步骤完成"}

    def on_error_callback(error):
        # 错误处理，返回错误信息
        return {"error": str(error), "recoverable": True}

    return stream_response(
        generator=token_generator(),
        event_type='progress',
        on_done=on_done_callback,
        on_error=on_error_callback
    )


@user_management_bp.route('/api/async-stream', methods=['GET'])
async def simple_async():
    """
    异步流式响应
    模拟异步 IO 操作（如调用外部 AI 接口）
    """

    async def my_async_generator():
        for i in range(1, 20):
            # 模拟异步等待（如 aiohttp 请求、数据库查询等）
            await asyncio.sleep(0.5)
            yield {"step": i, "content": f"异步生成第 {i} 条数据"}

    return stream_response(
        generator=my_async_generator()
    )


@user_management_bp.route('/api/sync-stream', methods=['GET'])
def simple_sync():
    """
    同步流式响应
    模拟同步 IO 操作（如调用外部 AI 接口）
    """

    def my_sync_generator():
        for i in range(1, 20):
            # 模拟同步等待（如 aiohttp 请求、数据库查询等）
            time.sleep(0.5)
            yield {"step": i, "content": f"同步生成第 {i} 条数据"}

    return stream_response(
        generator=my_sync_generator()
    )
