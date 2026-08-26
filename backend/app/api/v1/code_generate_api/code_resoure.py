import os

from flask import request

from backend.app.api.v1.code_generate_api import code_bp
from backend.app.common.emuns.constant import DEFAULT_GENERATE_ROOT, DEFAULT_DEPLOY_ROOT
from backend.app.common.exceptions.error_codes import ErrorCode
from backend.app.common.utils.auth import login_required
from backend.app.models.app_model import AppModel
from backend.app.schemas.responses.BaseResponse import directory_response, error_response


@code_bp.route('/static', methods=['GET'])
@login_required
def get_static_files():
    """
    获取静态资源文件
    ---
    tags:
      - 代码生成
    summary: 获取静态资源文件（预览/下载/目录列表）
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
    # 1. 获取并验证参数
    deploy_key = request.args.get('deploy_key')
    if not deploy_key:
        return error_response(ErrorCode.MISSING_PARAMETER, "deploy_key不能为空")

    # 2. 查询应用信息
    app = AppModel.query.filter_by(deploy_key=deploy_key, is_delete=0).first()
    if not app:
        return error_response(ErrorCode.APP_NOT_FOUND, "应用不存在")

    # 3. 构建应用目录部署路径
    app_dir = os.path.join(DEFAULT_GENERATE_ROOT, app.code_gen_type + "_" + str(app.id))
    if not os.path.exists(app_dir):
        return error_response(ErrorCode.APP_NOT_FOUND, "应用目录不存在，可能是应用未生成")
    app_deploy_dir = os.path.join(DEFAULT_DEPLOY_ROOT, deploy_key)

    # 4. 获取参数
    file_name = request.args.get('file_name')
    mode = request.args.get('mode', 'preview')  # 默认为预览模式

    # 5. 确定下载模式
    as_attachment = (mode == 'download')

    # 6. 调用统一的目录响应函数
    return directory_response(
        base_dir=app_deploy_dir,
        file_name=file_name,
        deploy_key=deploy_key,
        as_attachment=as_attachment
    )