import asyncio
import json
import json as json_module
import logging
import mimetypes
import os
import queue
import time as _time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Any, Generic, TypeVar, Union, Generator, AsyncGenerator, Callable

from flask import g, request
from flask import jsonify, Response, stream_with_context, after_this_request
from pydantic import BaseModel, Field

from backend.app.common.exceptions.error_codes import ErrorCode, BusinessException

_logger = logging.getLogger(__name__)

T = TypeVar('T')

# 模块级共享线程池，跨请求复用（SSE 长连接场景）
# max_workers=32 对于开发环境和一般生产已足够；可按需调大
_executor = ThreadPoolExecutor(max_workers=32, thread_name_prefix='async-gen')


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

    # 创建事件循环并提交到共享线程池
    loop = asyncio.new_event_loop()
    future = _executor.submit(run_thread, loop)

    # 主线程从队列中读取数据
    try:
        while True:
            item = q.get()
            if item is sentinel:
                break
            if isinstance(item, tuple) and item[0] == 'error':
                raise item[1]
            yield item
    finally:
        # 确保线程池任务完成，异常能被正确传播
        future.result()


def stream_response(
        generator: Union[Generator, AsyncGenerator],
        use_wrapper: bool = True,
        on_done: Callable = None,
        on_error: Callable = None
):
    """
    构造流式响应（SSE - Server-Sent Events）

    支持同步生成器和异步生成器，请尽量使用同步生成器，除非确定并发数非常高。
    异步生成器会自动转换为同步生成器，兼容所有部署方式。

    Args:
        generator: 生成器对象，每次产出一个 tuple (event, data)（支持同步/异步生成器），低并发请求（<10）建议使用同步生成器
        use_wrapper: 是否将每个数据块包装为统一响应体格式 ApiResponse
        on_done: 生成器完成后的回调函数（可选），签名为: on_done(chunks: list)
                 chunks 为生成器产出的所有原始数据块列表
        on_error: 生成器发生错误时的回调函数（可选），签名为: on_error(error: Exception, chunks: list)

    Returns:
        Flask Response 对象（流式）
    """

    def _wrap_chunk(event: str, data: Any) -> str:
        """将数据块包装为 SSE 格式"""
        if use_wrapper:
            response = ApiResponse(
                code=20000,
                message="操作成功",
                data=data
            )
            data_str = json_module.dumps(response.model_dump(mode='json'), ensure_ascii=False)
        else:
            if isinstance(data, (dict, list)):
                data_str = json_module.dumps(data, ensure_ascii=False)
            else:
                data_str = str(data)
        return f'event: {event}\ndata: {data_str}\n\n'

    # 判断生成器类型，将异步生成器转换为同步生成器
    is_async = hasattr(generator, '__anext__')
    if is_async:
        generator = async_generator_to_sync(generator)

    def _get_user_name_for_log() -> str:
        """获取用户 name 用于日志"""
        try:
            cur = getattr(g, 'current_user_name', None)
            if cur:
                return f"user:{cur}"
        except Exception as e:
            _logger.error(f"获取当前 user_name 失败: {e}")
        return "anonymous"

    def generate_sync():
        """同步生成器包装（统一处理所有生成器 + SSE 生命周期日志）

        日志级别：
            SSE_START  → INFO（请求进入，流即将开始）
            SSE_DONE   → INFO（流正常结束）
            SSE_ERROR  → ERROR（生成器抛异常，流中途失败）
            SSE_ABORT  → WARNING（客户端主动断开连接）
        """
        # ── 流开始时记录元信息 ──
        _stream_start = _time.perf_counter()
        _chunk_count = 0
        _user_tag = _get_user_name_for_log()
        _path_tag = request.path.rstrip('/') or '/'

        _logger.info(
            f"[SSE_START] {_user_tag} path={_path_tag} method={request.method}"
        )

        # 收集生成器产出的所有原始数据块，用于回调
        all_chunks = []
        _aborted = False     # GeneratorExit → 客户端断开
        _errored = False     # Exception → 业务异常

        try:
            for event, data in generator:
                _chunk_count += 1
                all_chunks.append((event, data))
                yield _wrap_chunk(event, data)
        except GeneratorExit:
            # Flask 在客户端主动断开连接时会关闭底层迭代器，抛 GeneratorExit
            # 这不是错误，是正常的中止信号（类似 HTTP 499 Client Closed Request）
            _aborted = True
        except Exception as e:
            _errored = True
            # ── 流异常：先记日志，再生成 error chunk 推给前端 ──
            _elapsed = (_time.perf_counter() - _stream_start) * 1000
            _logger.error(
                f"[SSE_ERROR] {_user_tag} path={_path_tag} "
                f"chunks={_chunk_count} elapsed={_elapsed/1000:.1f}s "
                f"error={type(e).__name__}: {str(e)}",
                exc_info=True   # 带完整堆栈，方便排查
            )
            if on_error:
                error_result = on_error(e, all_chunks)
                if error_result:
                    yield _wrap_chunk('error', error_result)
            else:
                if isinstance(e, BusinessException):
                    error_response_data = ApiResponse(
                        code=e.code, message=e.message, data=e.data
                    )
                else:
                    error_response_data = ApiResponse(
                        code=ErrorCode.INTERNAL_ERROR.code,
                        message=str(e) or ErrorCode.INTERNAL_ERROR.message,
                        data=None
                    )
                yield _wrap_chunk('error', error_response_data)
        finally:
            _elapsed = (_time.perf_counter() - _stream_start) * 1000

            if _aborted:
                # ── 客户端主动断开（WARNING 级别，因为不是后端的问题，但需要关注频率）──
                _logger.warning(
                    f"[SSE_ABORT] {_user_tag} path={_path_tag} "
                    f"chunks={_chunk_count} elapsed={_elapsed/1000:.1f}s"
                )
            elif not _errored:
                # ── 流正常结束 ──
                _logger.info(
                    f"[SSE_DONE] {_user_tag} path={_path_tag} "
                    f"chunks={_chunk_count} elapsed={_elapsed/1000:.1f}s"
                )

            # ── 回调 & done 事件 ──（不管成功/异常都要发 done 信号给前端）──
            if on_done:
                done_event = on_done(all_chunks) or json.dumps({})
            else:
                done_event = ApiResponse(code=20000, message="流结束", data=None)

            # 客户端断开时 Flask 可能已经关闭连接，yield 会抛 BrokenPipeError
            # 这里 try-except 保护一下，避免 finally 里的二次异常覆盖主异常
            try:
                yield _wrap_chunk('done', done_event)
            except (BrokenPipeError, ConnectionResetError):
                _logger.debug(
                    f"[SSE_DONE_SKIP] {_user_tag} path={_path_tag} "
                    f"客户端已断开，跳过 done 事件发送"
                )

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


def _validate_file_path(file_path: str, not_found_code: ErrorCode) -> tuple[bool, tuple | None]:
    """验证文件路径是否为合法的已存在文件，返回 (是否有效, 错误响应对象)"""
    if not os.path.exists(file_path):
        return False, error_response(not_found_code, f"文件不存在: {file_path}")
    if not os.path.isfile(file_path):
        return False, error_response(ErrorCode.INVALID_PARAMETER, f"不是文件: {file_path}")
    return True, None


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
    # 1. 验证文件合法性
    is_valid, err = _validate_file_path(file_path, ErrorCode.APP_NOT_FOUND)
    if not is_valid:
        return err

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
        as_attachment: bool = False,
        download_name: str = None
):
    """
    通用文件响应（单个文件的预览或下载）

    作为最底层的通用方法，只负责返回单个文件，不处理目录列表。
    调用方需确保 base_dir 指向合法的文件绝对路径。

    Args:
        base_dir: 文件的绝对路径
        as_attachment: 是否作为附件下载，False为在线预览，True为下载
        download_name: 下载时的文件名（可选，默认使用原始文件名）

    Returns:
        Flask文件响应或错误响应
    """
    # 1. 验证文件合法性
    is_valid, err = _validate_file_path(base_dir, ErrorCode.FILE_NOT_FOUND)
    if not is_valid:
        return err

    # 2. 默认下载文件名
    if not download_name:
        download_name = os.path.basename(base_dir)

    # 3. 委托给 file_response 返回
    return file_response(
        file_path=base_dir,
        as_attachment=as_attachment,
        download_name=download_name
    )
