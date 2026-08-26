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
    获取静态资源文件，支持在线预览和下载两种模式

    访问完整路径示例：
    - 在线预览HTML：http://localhost:5000/api/v1/code/static?deploy_key=xxx&file_name=index.html
    - 下载单个文件：http://localhost:5000/api/v1/code/static?deploy_key=xxx&file_name=index.html&mode=download
    - 获取目录列表：http://localhost:5000/api/v1/code/static?deploy_key=xxx

    参数说明：
    deploy_key：应用部署key，必填
    file_name：文件名（支持相对路径），可选；不传则返回目录列表
    mode：文件返回模式，可选值：
           - preview（默认，在线预览，浏览器根据Content-Type自动渲染）
           - download（下载模式，触发浏览器下载对话框）

    返回：
    - 有 file_name 时：返回单个文件内容
    - 无 file_name 时：返回目录下所有文件的列表（JSON格式）
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
