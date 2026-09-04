import os

from flask import request

from backend.app.api.v1.code_generate_api import code_bp
from backend.app.common.emuns.constant import DEFAULT_GENERATE_ROOT, DEFAULT_DEPLOY_ROOT
from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException
from backend.app.common.utils.auth import login_required
from backend.app.schemas.responses.BaseResponse import error_response, success_response
from backend.app.services.app_service import get_app_by_deploy_key, get_app_by_id
from backend.app.services.static_file_service import build_static_response, build_app_zip_response


@code_bp.route('/static', methods=['GET'])
def get_static_deployed_app_files():
    """
    获取已部署应用的静态资源文件
    ---
    tags:
      - 代码生成
    summary: 获取已生成且已部署静态资源文件（预览/下载/目录列表）
    description: |
      根据部署Key获取应用的静态资源文件，支持三种模式：
      1. 在线预览：浏览器根据Content-Type自动渲染（如HTML图片）
      2. 下载文件：触发浏览器下载对话框
      3. 目录列表：返回应用下所有文件的信息列表
      
      使用示例：
      - 在线预览HTML：GET /api/v1/code/static?deploy_key=xxx&file_name=index.html
      - 下载单个文件：GET /api/v1/code/static?deploy_key=xxx&file_name=index.html&mode=download
      - 获取目录列表：GET /api/v1/code/static?deploy_key=xxx
    produces:
      - text/html
      - text/css
      - application/javascript
      - image/png
      - application/octet-stream
      - application/json
    parameters:
      - in: header
        name: Authorization
        required: true
        type: string
        description: JWT Token，格式为 "Bearer <token>"
      - in: query
        name: deploy_key
        required: true
        type: string
        description: 应用部署Key
        example: abc123def456
      - in: query
        name: file_name
        required: false
        type: string
        description: |
          文件名（支持相对路径，如 css/style.css）。
          不传则返回整个目录的文件列表
        example: index.html
      - in: query
        name: mode
        required: false
        type: string
        description: |
          文件返回模式：
          - preview（默认）：在线预览，浏览器根据Content-Type自动渲染
          - download：下载模式，触发浏览器下载对话框
        enum: ['preview', 'download']
        default: preview
    responses:
      200:
        description: |
          成功响应，根据file_name参数返回不同内容：
          - 有file_name：返回文件内容（Content-Type根据文件类型自动设置）
          - 无file_name：返回目录列表JSON
          
          目录列表响应示例：
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
                total:
                  type: integer
                  example: 5
                files:
                  type: array
                  items:
                    type: object
                    properties:
                      file_name:
                        type: string
                        example: index.html
                      file_size:
                        type: integer
                        example: 1024
                      mime_type:
                        type: string
                        example: text/html
                      file_url:
                        type: string
                        example: /api/v1/code/static?deploy_key=xxx&file_name=index.html
                      modified_time:
                        type: number
                        example: 1720000000.0
      400:
        description: 请求参数错误（如deploy_key缺失）
      401:
        description: 未登录或Token无效
      405:
        description: 应用不存在或文件不存在
    """
    deploy_key = request.args.get('deploy_key')
    file_name = request.args.get('file_name')
    if not deploy_key:
        return error_response(ErrorCode.MISSING_PARAMETER, "deploy_key不能为空")

    # 校验应用存在
    app = get_app_by_deploy_key(deploy_key)
    if not app:
        return error_response(ErrorCode.APP_NOT_FOUND, "应用不存在，请确认是否已生成")

    # 校验部署目录存在
    app_dir = os.path.join(DEFAULT_DEPLOY_ROOT, deploy_key)
    if not os.path.exists(app_dir):
        return error_response(ErrorCode.APP_NOT_FOUND, "应用目录不存在，请确认是否已部署")

    try:
        is_response, data = build_static_response(
            identifier=deploy_key,
            file_name=file_name,
            search_roots=[DEFAULT_DEPLOY_ROOT],
            mode=request.args.get('mode', 'preview'),
        )
        if is_response:
            return data
        return success_response(data)
    except BusinessException as e:
        return error_response(e.error_code, e.message, e.data)


@code_bp.route('/static/<string:generated_path>', methods=['GET'])
def get_static_generated_app_files_by_path(generated_path: str):
    """
    获取已生成应用的所有静态资源文件，用于预览/下载
    ---
    tags:
      - 代码生成
    summary: 获取已生成静态资源文件（预览/下载/目录列表）
    description: |
      根据部署Key获取应用的静态资源文件，支持三种模式：
      1. 在线预览：浏览器根据Content-Type自动渲染（如HTML图片）
      2. 下载文件：触发浏览器下载对话框
      3. 目录列表：返回应用下所有文件的信息列表

      使用示例：
      - 在线预览HTML：GET /api/v1/code/static?deploy_key=xxx&file_name=index.html
      - 下载单个文件：GET /api/v1/code/static?deploy_key=xxx&file_name=index.html&mode=download
      - 获取目录列表：GET /api/v1/code/static?deploy_key=xxx
    parameters:
      - in: path
        name: generated_path
        type: string
        required: true
        type: string
        description: 应用生成路径，格式为 "code_gen_type_id"
    responses:
      200:
        description: 成功响应，返回应用下所有文件的信息列表JSON
      405:
        description: 应用不存在或文件不存在
    """
    app_id = generated_path.split('_')[-1]
    app = get_app_by_id(int(app_id))
    if not app:
        return error_response(ErrorCode.APP_NOT_FOUND, "应用不存在，请确认是否已生成")

    try:
        is_response, data = build_static_response(
            identifier=generated_path,
            file_name=None,
            search_roots=[DEFAULT_GENERATE_ROOT],
        )
        if is_response:
            return data
        return success_response(data)
    except BusinessException as e:
        return error_response(e.error_code, e.message, e.data)


# ==================== 内部辅助（已迁到 static_file_service.py）====================


# 新增：路径参数路由（为了支持相对路径自动解析）
@code_bp.route('/static/<string:identifier>/<path:file_name>', methods=['GET'])
def get_static_file_by_path(identifier, file_name):
    """
    路径参数形式的静态资源接口
    - 支持HTML中的相对路径自动解析（不需要修改AI生成的代码）
    - 示例：/api/v1/code/static/8qEDDL/index.html
    - 浏览器会自动将HTML中的href="css/style.css"解析为：
      /api/v1/code/static/8qEDDL/css/style.css
    """
    try:
        is_response, data = build_static_response(
            identifier=identifier,
            file_name=file_name,
            search_roots=[DEFAULT_DEPLOY_ROOT, DEFAULT_GENERATE_ROOT],
            mode=request.args.get('mode', 'preview'),
        )
        if is_response:
            return data
        return success_response(data)
    except BusinessException as e:
        return error_response(e.error_code, e.message, e.data)


@code_bp.route('/app/download/<int:app_id>', methods=['GET'])
@login_required
def download_app_code(app_id: int):
    """
    打包下载应用的所有代码文件为ZIP压缩包
    ---
    tags:
      - 代码生成
    summary: 下载应用的代码文件压缩包
    description: |
      根据应用ID，将该应用的所有代码文件打包为ZIP格式供浏览器下载。
      自动搜索 GENERATE_ROOT 和 DEPLOY_ROOT 下的应用目录。

      使用示例：
      - GET /api/v1/code/app/download/47
    parameters:
      - in: header
        name: Authorization
        required: true
        type: string
        description: JWT Token，格式为 "Bearer <token>"
      - in: path
        name: app_id
        required: true
        type: integer
        description: 应用ID
    responses:
      200:
        description: 返回ZIP压缩包文件
      404:
        description: 应用不存在或目录不存在
    """
    app = get_app_by_id(app_id)
    if not app:
        return error_response(ErrorCode.APP_NOT_FOUND, "应用不存在")

    generated_path = f"{app.code_gen_type}_{app_id}"
    app_dir = os.path.join(DEFAULT_GENERATE_ROOT, generated_path)

    if not os.path.exists(app_dir):
        return error_response(ErrorCode.APP_NOT_FOUND, "应用目录不存在，可能是应用未生成")

    try:
        return build_app_zip_response(app_dir, f"{app.app_name}.zip")
    except BusinessException as e:
        return error_response(e.error_code, e.message, e.data)
