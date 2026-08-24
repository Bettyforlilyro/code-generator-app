import asyncio
import queue
import threading
from typing import Optional, Any, Generic, TypeVar, Union, Generator, AsyncGenerator, Callable

from flask import jsonify, Response, stream_with_context
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