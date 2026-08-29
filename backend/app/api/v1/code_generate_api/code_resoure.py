import mimetypes
import os

from flask import request

from backend.app.api.v1.code_generate_api import code_bp
from backend.app.common.emuns.constant import DEFAULT_GENERATE_ROOT, DEFAULT_DEPLOY_ROOT
from backend.app.common.exceptions.error_codes import ErrorCode
from backend.app.models.app_model import AppModel
from backend.app.schemas.responses.BaseResponse import directory_response, error_response, success_response


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
    # 1. 验证参数
    deploy_key = request.args.get('deploy_key')
    file_name = request.args.get('file_name')
    if not deploy_key:
        return error_response(ErrorCode.MISSING_PARAMETER, "deploy_key不能为空")

    # 2. 查询应用信息
    app = AppModel.query.filter_by(deploy_key=deploy_key, is_delete=0).first()
    if not app:
        return error_response(ErrorCode.APP_NOT_FOUND, "应用不存在，请确认是否已生成")

    # 3. 构建应用目录路径
    app_dir = os.path.join(DEFAULT_DEPLOY_ROOT, deploy_key)
    if not os.path.exists(app_dir):
        return error_response(ErrorCode.APP_NOT_FOUND, "应用目录不存在，请确认是否已部署")

    return _handle_static_request(deploy_key, file_name, search_roots=[DEFAULT_DEPLOY_ROOT])


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
    app = AppModel.query.filter_by(id=app_id, is_delete=0).first()
    if not app:
        return error_response(ErrorCode.APP_NOT_FOUND, "应用不存在，请确认是否已生成")
    # 2. 构建应用目录路径
    return _handle_static_request(generated_path, None, search_roots=[DEFAULT_GENERATE_ROOT])


def _list_directory(base_dir: str, identifier: str):
    """
    递归列出目录下的所有文件，返回目录列表JSON响应。

    Args:
        base_dir: 应用的基础目录（绝对路径）
        identifier: 标识符（deploy_key 或 generated_path），用于拼接文件访问URL

    Returns:
        统一格式的目录列表响应
    """
    files_list = []
    for root, dirs, files in os.walk(base_dir):
        relative_path = os.path.relpath(root, base_dir)
        for file in files:
            file_full_path = os.path.join(root, file)
            file_relative_path = os.path.join(relative_path, file) if relative_path != '.' else file

            file_stat = os.stat(file_full_path)
            mime_type, _ = mimetypes.guess_type(file_full_path)
            relative_slash = file_relative_path.replace('\\', '/')

            file_info = {
                'file_name': relative_slash,
                'file_size': file_stat.st_size,
                'mime_type': mime_type or 'application/octet-stream',
                'file_url': f'/api/v1/code/static/{identifier}/{relative_slash}',
                'preview_url': f'/api/v1/code/static/{identifier}/{relative_slash}',
                'download_url': f'/api/v1/code/static/{identifier}/{relative_slash}?mode=download',
                'modified_time': file_stat.st_mtime
            }
            files_list.append(file_info)

    files_list.sort(key=lambda x: x['file_name'])

    return success_response({
        'total': len(files_list),
        'files': files_list
    })


# 抽离核心逻辑为公共函数
# 替换第 220-254 行的 _handle_static_request

def _handle_static_request(identifier, file_name, search_roots=None):
    """
    核心静态资源处理逻辑

    Args:
        identifier: 目录标识符（deploy_key 或 generated_path）
        file_name: 文件名（None 表示目录列表）
        search_roots: 要搜索的根目录列表，None 则默认 [DEPLOY_ROOT, GENERATE_ROOT]
    """
    if search_roots is None:
        search_roots = [DEFAULT_DEPLOY_ROOT, DEFAULT_GENERATE_ROOT]

    for root_dir in search_roots:
        app_dir = os.path.join(root_dir, identifier)
        if not os.path.exists(app_dir):
            continue

        if file_name:
            # 返回单个文件（含路径穿越检查）
            safe_base = os.path.realpath(app_dir)
            target_path = os.path.realpath(os.path.join(app_dir, file_name))

            if not target_path.startswith(safe_base):
                return error_response(ErrorCode.INVALID_PARAMETER, "非法的文件路径")

            mode = request.args.get('mode', 'preview')
            as_attachment = (mode == 'download')
            return directory_response(
                base_dir=target_path,
                as_attachment=as_attachment,
                download_name=file_name
            )
        else:
            # 返回目录列表
            return _list_directory(app_dir, identifier)

    # 所有根目录都找不到
    return error_response(ErrorCode.APP_NOT_FOUND, f"应用目录不存在: {identifier}")


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
    # 复用核心逻辑
    return _handle_static_request(identifier, file_name)


