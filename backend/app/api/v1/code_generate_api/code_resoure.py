import os.path

from flask import request

from backend.app.api.v1.code_generate_api import code_bp
from backend.app.common.emuns.constant import DEFAULT_GENERATE_ROOT
from backend.app.common.exceptions.error_codes import ErrorCode
from backend.app.common.utils.auth import login_required
from backend.app.models.app_model import AppModel
from backend.app.schemas.responses.BaseResponse import error_response, success_response
from backend.app.schemas.responses.resource_response import ResourceFileResponse, ResourceFileNode, \
    ResourceFileListResponse


@code_bp.route('/static', methods=['GET'])
@login_required
def get_static_files():
    """
    获取静态资源文件，主要是生成的代码文件（如HTML、CSS、JS等文件），也可能是png/jpeg等图片文件，提供给前端展示
    访问完整路径示例：http://localhost:5000/api/v1/code/static?deploy_key=123456&file_name=index.html
    参数说明：
    deploy_key：应用部署key，必填
    file_name：文件名，可选，默认index.html
    返回：
    如果有file_name，返回单个文件；否则返回文件目录下的所有文件资源（包括子目录下的文件）
    """
    deploy_key = request.args.get('deploy_key')
    if not deploy_key:
        return error_response(ErrorCode.MISSING_PARAMETER, "deploy_key不能为空")
    app = AppModel.query.filter_by(deploy_key=deploy_key, is_deleted=0).first()
    if not app:
        return error_response(ErrorCode.APP_NOT_FOUND, "应用不存在")
    app_dir = os.path.join(DEFAULT_GENERATE_ROOT, app.code_gen_type + "_" + deploy_key)
    if not os.path.exists(app_dir):
        return error_response(ErrorCode.APP_NOT_FOUND, "应用目录不存在，可能是应用未生成")
    file_name = request.args.get('file_name')
    if file_name:
        file_path = os.path.join(app_dir, file_name)
        if not os.path.exists(file_path):
            return error_response(ErrorCode.FILE_NOT_FOUND, "文件不存在")
        # 返回文件
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        file_size = os.path.getsize(file_path)
        relative_path = os.path.relpath(file_path, app_dir).replace('\\', '/')
        file_response = ResourceFileResponse(
            file_name=os.path.basename(file_path),
            relative_path=relative_path,
            content=content,
            size=file_size
        )
        return success_response(file_response)
    else:
        # 返回目录下的所有文件资源（包括子目录下的文件），含文件内容
        def build_file_node(current_path, base_dir):
            """递归构建文件/目录节点"""
            name = os.path.basename(current_path)
            relative = os.path.relpath(current_path, base_dir).replace('\\', '/')
            if os.path.isdir(current_path):
                children = []
                for item in sorted(os.listdir(current_path)):
                    item_path = os.path.join(current_path, item)
                    children.append(build_file_node(item_path, base_dir))
                return ResourceFileNode(
                    name=name,
                    path=relative,
                    is_dir=True,
                    size=0,
                    content=None,
                    children=children
                )
            else:
                file_size = os.path.getsize(current_path)
                try:
                    with open(current_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                except (UnicodeDecodeError, IOError):
                    file_content = "[二进制文件，无法预览内容]"
                return ResourceFileNode(
                    name=name,
                    path=relative,
                    is_dir=False,
                    size=file_size,
                    content=file_content,
                    children=None
                )

        root_nodes = []
        for item in sorted(os.listdir(app_dir)):
            item_path = os.path.join(app_dir, item)
            root_nodes.append(build_file_node(item_path, app_dir))

        # 统计文件总数
        def count_files(nodes):
            count = 0
            for node in nodes:
                if not node.is_dir:
                    count += 1
                elif node.children:
                    count += count_files(node.children)
            return count

        list_response = ResourceFileListResponse(
            deploy_id=deploy_key,
            root_path=app_dir,
            files=root_nodes,
            total_files=count_files(root_nodes)
        )
        return success_response(list_response)
