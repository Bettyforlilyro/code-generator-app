"""
静态文件 Service 层

负责：路径安全校验、目录列表、单文件响应、ZIP 打包下载
"""
import io
import mimetypes
import os
import zipfile
from typing import Optional
from urllib.parse import quote

from flask import send_file

from backend.app.common.exceptions.error_codes import BusinessException, ErrorCode
from backend.app.schemas.responses.BaseResponse import directory_response


# ==================== 路径工具 ====================

def build_app_dir_path(root: str, identifier: str) -> str:
    """拼接应用目录完整路径"""
    return os.path.join(root, identifier)


def find_app_dir(identifier: str, search_roots: list[str]) -> str | None:
    """
    在多个根目录中查找应用目录

    Args:
        identifier: 目录标识符（deploy_key 或 generated_path）
        search_roots: 要搜索的根目录列表

    Returns:
        找到的绝对路径，找不到返回 None
    """
    for root_dir in search_roots:
        app_dir = os.path.join(root_dir, identifier)
        if os.path.exists(app_dir):
            return app_dir
    return None


def ensure_safe_path(base_dir: str, file_path: str) -> str:
    """
    路径穿越安全校验

    Args:
        base_dir: 允许访问的基础目录
        file_path: 用户传入的文件路径（可能含 ../）

    Returns:
        校验通过的绝对路径

    Raises:
        BusinessException: 路径非法（穿越出基础目录）
    """
    safe_base = os.path.realpath(base_dir)
    target_path = os.path.realpath(os.path.join(base_dir, file_path))

    if not target_path.startswith(safe_base):
        raise BusinessException(ErrorCode.INVALID_PARAMETER, "非法的文件路径")

    return target_path


# ==================== 目录列表 ====================

def list_directory(base_dir: str, identifier: str) -> dict:
    """
    递归列出目录下所有文件，返回结构化列表

    Args:
        base_dir: 应用基础目录绝对路径
        identifier: 标识符（deploy_key / generated_path），用于拼接访问 URL

    Returns:
        {'total': N, 'files': [...]} 格式的字典
    """
    files_list = []
    for root, _dirs, files in os.walk(base_dir):
        relative_path = os.path.relpath(root, base_dir)
        for file_name in files:
            file_full_path = os.path.join(root, file_name)
            file_relative_path = (
                file_name if relative_path == '.'
                else os.path.join(relative_path, file_name)
            )

            file_stat = os.stat(file_full_path)
            mime_type, _ = mimetypes.guess_type(file_full_path)
            relative_slash = file_relative_path.replace('\\', '/')

            files_list.append({
                'file_name': relative_slash,
                'file_size': file_stat.st_size,
                'mime_type': mime_type or 'application/octet-stream',
                'file_url': f'/api/v1/code/static/{identifier}/{relative_slash}',
                'preview_url': f'/api/v1/code/static/{identifier}/{relative_slash}',
                'download_url': f'/api/v1/code/static/{identifier}/{relative_slash}?mode=download',
                'modified_time': file_stat.st_mtime,
            })

    files_list.sort(key=lambda x: x['file_name'])
    return {'total': len(files_list), 'files': files_list}


# ==================== 单文件 / 目录响应 ====================

def build_static_response(
    identifier: str,
    file_name: Optional[str],
    search_roots: list[str],
    mode: str = 'preview',
) -> tuple[bool, object]:
    """
    构建静态资源响应（目录列表 / 单文件预览 / 单文件下载）

    Args:
        identifier: 目录标识符
        file_name: 文件名，None 表示目录列表
        search_roots: 搜索的根目录列表
        mode: 'preview' 或 'download'

    Returns:
        (is_flask_response, data) 元组：
        - is_flask_response=True  → data 是 Flask Response（send_file / directory_response）
        - is_flask_response=False → data 是 dict，需要路由层包装成 success_response
    """
    app_dir = find_app_dir(identifier, search_roots)
    if not app_dir:
        raise BusinessException(
            ErrorCode.APP_NOT_FOUND,
            f"应用目录不存在: {identifier}"
        )

    if file_name:
        target_path = ensure_safe_path(app_dir, file_name)
        as_attachment = (mode == 'download')
        return True, directory_response(
            base_dir=target_path,
            as_attachment=as_attachment,
            download_name=file_name,
        )

    # 目录列表
    return False, list_directory(app_dir, identifier)


# ==================== ZIP 打包下载 ====================

def build_app_zip_response(app_dir: str, zip_filename: str):
    """
    将应用目录打包成 ZIP 并返回下载响应

    Args:
        app_dir: 应用代码目录
        zip_filename: 下载的 ZIP 文件名（可能含中文）

    Returns:
        Flask Response 对象（send_file）
    """
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(app_dir):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                arcname = os.path.relpath(file_path, app_dir).replace('\\', '/')
                zf.write(file_path, arcname)

    memory_file.seek(0)

    # 统一的中文文件名编码
    encoded = quote(zip_filename)
    content_disposition = (
        f'attachment; filename="{encoded}"; '
        f'filename*=UTF-8\'\'{encoded}'
    )

    response = send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=False,
    )
    response.headers['Content-Disposition'] = content_disposition
    return response
