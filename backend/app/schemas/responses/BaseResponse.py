import asyncio
import mimetypes
import os
import queue
import threading
from typing import Optional, Any, Generic, TypeVar, Union, Generator, AsyncGenerator, Callable

from flask import jsonify, Response, stream_with_context, after_this_request
from pydantic import BaseModel, Field

from backend.app.common.exceptions.error_codes import ErrorCode

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """统一响应体"""
    code: int = Field(20000, description="业务状态码")
    message: str = Field("操作成功", description="提示信息")
    data: Optional[T] = Field(None, description="业务数据")


def success_response(data: Any = None, http_status: int = 200):
    """
    构造成功响应

    Args:
        data: 响应数据
        http_status: HTTP响应状态码，默认200

    Returns:
        Flask JSON响应对象
    """
    response = ApiResponse(
        code=20000,
        message="操作成功",
        data=data
    )
    return jsonify(response.model_dump()), http_status


def error_response(code: Union[int, ErrorCode], message: str = None, data: dict = None, http_status: int = 500):
    """
    构造错误响应

    Args:
        code: 业务错误码（可以是int或ErrorCode枚举）
        message: 错误描述（可选，当code为ErrorCode时可自动获取）
        data: 附加的错误详情（可选）
        http_status: HTTP状态码（可选，如果没有传入此参数，使用ErrorCode中相关联的错误码）

    Returns:
        Flask JSON响应对象
    """
    # 处理不同类型的code参数
    if isinstance(code, ErrorCode):
        actual_code = code.code
        actual_message = message or code.message
    elif isinstance(code, int):
        actual_code = code
        actual_message = message or "未知错误，后端忘记填错误码描述了"
    else:
        raise TypeError(f"code参数必须是int或ErrorCode类型，当前类型: {type(code)}")

    response = ApiResponse(
        code=actual_code,
        message=actual_message,
        data=data
    )
    # 如果HTTP响应码未使用默认的500，则使用传入的http_status作为响应码，否则取自定义错误码的前三位，具体参见error_codes.py文件中定义的内容
    http_code = http_status if http_status != 500 else actual_code // 100
    return jsonify(response.model_dump(mode='json')), http_code


def async_generator_to_sync(async_gen: AsyncGenerator) -> Generator:
    """
    将异步生成器转换为同步生成器

    使用一个后台线程运行异步生成器，通过队列将数据传递给主线程。
    这样无论 Flask 路由是同步还是异步，都能正确处理异步生成器。

    Args:
        async_gen: 异步生成器对象

    Yields:
        同步生成器产出的数据块
    """
    # 使用队列在异步线程和主线程之间传递数据
    q = queue.Queue()
    sentinel = object()  # 哨兵对象，标识生成器结束

    async def run_async():
        """在异步事件循环中运行异步生成器"""
        try:
            async for item in async_gen:
                q.put(item)
        except Exception as e:
            q.put(('error', e))
        finally:
            q.put(sentinel)

    def run_thread(loop):
        """在新线程中运行事件循环"""
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_async())
        loop.close()

    # 创建新的事件循环和线程
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=run_thread, args=(loop,), daemon=True)
    thread.start()

    # 主线程从队列中读取数据
    while True:
        item = q.get()
        if item is sentinel:
            break
        if isinstance(item, tuple) and item[0] == 'error':
            raise item[1]
        yield item

    thread.join()


def stream_response(
        generator: Union[Generator, AsyncGenerator],
        event_type: str = 'message',
        use_wrapper: bool = True,
        on_done: Callable = None,
        on_error: Callable = None
):
    """
    构造流式响应（SSE - Server-Sent Events）

    支持同步生成器和异步生成器，请尽量使用同步生成器，除非确定并发数非常高。
    异步生成器会自动转换为同步生成器，兼容所有部署方式。

    Args:
        generator: 生成器对象，每次产出一个数据块（支持同步/异步生成器），低并发请求（<10）建议使用同步生成器
        event_type: SSE事件类型，默认为 'message'
        use_wrapper: 是否将每个数据块包装为统一响应体格式 ApiResponse
        on_done: 生成器完成后的回调函数（可选）
        on_error: 生成器发生错误时的回调函数（可选）

    Returns:
        Flask Response 对象（流式）
    """
    import json as json_module

    def _wrap_chunk(chunk: Any) -> str:
        """将数据块包装为 SSE 格式"""
        if use_wrapper:
            # 使用统一响应体包装
            response = ApiResponse(
                code=20000,
                message="操作成功",
                data=chunk
            )
            data_str = json_module.dumps(response.model_dump(mode='json'), ensure_ascii=False)
        else:
            # 直接序列化数据
            if isinstance(chunk, (dict, list)):
                data_str = json_module.dumps(chunk, ensure_ascii=False)
            else:
                data_str = str(chunk)

        return f'event: {event_type}\ndata: {data_str}\n\n'

    # 判断生成器类型，将异步生成器转换为同步生成器
    is_async = hasattr(generator, '__anext__')
    if is_async:
        generator = async_generator_to_sync(generator)

    def generate_sync():
        """同步生成器包装（统一处理所有生成器）"""
        try:
            for chunk in generator:
                yield _wrap_chunk(chunk)
        except Exception as e:
            if on_error:
                error_result = on_error(e)
                if error_result:
                    yield _wrap_chunk(error_result)
            else:
                # 默认错误处理
                error_response_data = ApiResponse(
                    code=50000,
                    message=str(e),
                    data=None
                )
                yield f'event: error\ndata: {json_module.dumps(error_response_data.model_dump(mode="json"), ensure_ascii=False)}\n\n'
        finally:
            if on_done:
                done_result = on_done()
                if done_result:
                    yield _wrap_chunk(done_result)
            # 发送完成事件，前端通过监听 done 事件判断流是否结束
            done_event = ApiResponse(code=20000, message="流结束", data=None)
            yield f'event: done\ndata: {json_module.dumps(done_event.model_dump(mode="json"), ensure_ascii=False)}\n\n'

    # 统一使用 stream_with_context 包装同步生成器
    # 保持请求上下文在整个流生命周期内有效
    return Response(
        stream_with_context(generate_sync()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


def file_response(
        file_path: str,
        as_attachment: bool = False,
        download_name: str = None,
        mimetype: str = None,
        headers: dict = None
):
    """
    构造文件响应（在线预览或下载）

    支持两种模式：
    1. 在线预览（as_attachment=False）：浏览器根据Content-Type自动渲染（如HTML图片）
    2. 下载（as_attachment=True）：触发浏览器下载对话框

    Args:
        file_path: 文件的绝对路径
        as_attachment: 是否作为附件下载，False为在线预览，True为下载
        download_name: 下载时的文件名（仅在as_attachment=True时生效）
        mimetype: 指定MIME类型，不传则自动检测
        headers: 额外的响应头

    Returns:
        Flask文件响应或错误响应
    """
    # 1. 验证文件是否存在
    if not os.path.exists(file_path):
        return error_response(ErrorCode.APP_NOT_FOUND, f"文件不存在: {file_path}")
    if not os.path.isfile(file_path):
        return error_response(ErrorCode.INVALID_PARAMETER, f"不是文件: {file_path}")

    # 2. 自动检测MIME类型
    if not mimetype:
        mimetype, _ = mimetypes.guess_type(file_path)
        if not mimetype:
            mimetype = 'application/octet-stream'

    # 3. 准备响应头
    response_headers = headers.copy() if headers else {}

    # 4. 如果是下载模式，设置Content-Disposition
    if as_attachment:
        if not download_name:
            download_name = os.path.basename(file_path)
        response_headers['Content-Disposition'] = f'attachment; filename="{download_name}"'
    else:
        # 在线预览模式，明确设置为inline
        response_headers['Content-Disposition'] = 'inline'

    def set_response_headers(resp):
        for key, value in response_headers.items():
            resp.headers[key] = value
        return resp

    after_this_request(set_response_headers)

    # 5. 使用send_file返回文件
    from flask import send_file
    return send_file(
        file_path,
        mimetype=mimetype,
        as_attachment=as_attachment,
        download_name=download_name
    )


def directory_response(
        base_dir: str,
        file_name: str = None,
        deploy_key: str = None,
        as_attachment: bool = False,
        download_name: str = None
):
    """
    构造目录或文件响应（静态资源统一入口）

    - 有file_name时：返回单个文件（支持在线预览/下载）
    - 无file_name时：返回目录列表（JSON格式）

    包含路径安全检查，防止路径穿越攻击。

    Args:
        base_dir: 基础目录（绝对路径）
        file_name: 文件名（支持相对路径，如css/style.css）
        deploy_key: 部署key（用于构建文件URL，目录列表时需要）
        as_attachment: 是否下载模式
        download_name: 下载文件名

    Returns:
        文件响应或目录列表响应
    """
    # 1. 验证基础目录
    if not os.path.exists(base_dir):
        return error_response(ErrorCode.APP_NOT_FOUND, f"目录不存在: {base_dir}")

    if file_name:
        # 返回单个文件
        # --- 路径安全检查 ---
        # 规范化路径，防止路径穿越
        safe_base = os.path.realpath(base_dir)
        target_path = os.path.realpath(os.path.join(base_dir, file_name))

        # 检查目标路径是否在基础目录内
        if not target_path.startswith(safe_base):
            return error_response(ErrorCode.INVALID_PARAMETER, "非法的文件路径")

        # --- 返回文件 ---
        return file_response(
            file_path=target_path,
            as_attachment=as_attachment,
            download_name=download_name or file_name
        )
    else:
        # 返回目录列表
        files_list = []

        # 递归扫描目录
        for root, dirs, files in os.walk(base_dir):
            relative_path = os.path.relpath(root, base_dir)

            for file in files:
                file_full_path = os.path.join(root, file)
                file_relative_path = os.path.join(relative_path, file) if relative_path != '.' else file

                # 获取文件信息
                file_stat = os.stat(file_full_path)
                mime_type, _ = mimetypes.guess_type(file_full_path)

                # 构建文件信息（路径统一用正斜杠）
                relative_slash = file_relative_path.replace('\\', '/')
                file_info = {
                    'file_name': relative_slash,
                    'file_size': file_stat.st_size,
                    'mime_type': mime_type or 'application/octet-stream',
                    'file_url': f'/api/v1/code/static?deploy_key={deploy_key}&file_name={relative_slash}',
                    'preview_url': f'/api/v1/code/static?deploy_key={deploy_key}&file_name={relative_slash}&mode=preview',
                    'download_url': f'/api/v1/code/static?deploy_key={deploy_key}&file_name={relative_slash}&mode=download',
                    'modified_time': file_stat.st_mtime
                }
                files_list.append(file_info)

        # 按文件名排序
        files_list.sort(key=lambda x: x['file_name'])

        return success_response({
            'total': len(files_list),
            'files': files_list
        })
