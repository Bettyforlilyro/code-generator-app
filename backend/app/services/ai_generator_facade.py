import json
import logging
import re

from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.common.exceptions.error_codes import (
    ErrorCode, AIServiceError, FileOperationError, BusinessException,
)
from backend.app.common.utils.code_file_saver import CodeFileSaverFactory
from backend.app.schemas.ai_generate_results import BaseCodeResult
from backend.app.schemas.requests.app_management_request import AppUpdateRequest
from backend.app.services.ai_common.advisor import StreamChunk
from backend.app.services.ai_common.chat_client_builder import ChatClientBuilder
from backend.app.services.ai_common.chat_memory import get_chat_memory_manager
from backend.app.services.app_service import update_app_svc, get_app_creator_by_app_id

logger = logging.getLogger(__name__)


def processed_chunk(chunk: StreamChunk):
    """
    处理流式响应，根据需要进行转换或过滤，简化 Chunk 内容

    :param chunk: 流式响应块
    :return: 处理后的数据块，真正 yield 给前端的数据格式（SSE 相应数据中 data 字段的内容）
    """
    msg_type = chunk.chunk_type
    if msg_type == StreamChunk.TYPE_TEXT:
        return {"d": chunk.content}
    elif msg_type == StreamChunk.TYPE_TOOL_START:
        return {"t": "tool_start", "tool_info": chunk.content, "extra": chunk.metadata}
    elif msg_type == StreamChunk.TYPE_TOOL_END:
        return {"t": "tool_end", "tool_info": chunk.content, "extra": chunk.metadata}


class AICodeGeneratorFacade:
    """AI代码生成器外观类"""
    @staticmethod
    def generate_code_and_save_file(user_message: str, code_gen_type: CodeFileType, app_id: int):
        """生成代码并保存文件，返回保存路径"""
        pydantic_model = CodeFileType.get_cls_type(code_gen_type)
        memory_manager = get_chat_memory_manager()
        messages = memory_manager.get_llm_messages(
            app_id=app_id,
            extra_messages=[{"role": "user", "content": user_message}]
        )
        # 1. 调用AI模型生成代码
        llm_client = (ChatClientBuilder()
                      .set_response_format(pydantic_model.get_response_format())
                      .set_system_prompt("")    # system_prompt已经存到数据库中了，从messages中已经有了
                      .build())
        response = llm_client.chat_structured(messages, pydantic_model)
        # 2. 保存代码到文件
        saver = CodeFileSaverFactory.get_saver(code_gen_type)
        file_save_path = saver.save_code_file(response, app_id)
        return file_save_path

    @staticmethod
    def generate_code_and_save_file_streaming(user_message: str,
                                              code_gen_type: CodeFileType,
                                              app_id: int,
                                              tools: list = None,
                                              ):
        """
        流式生成代码并保存文件的生成器（纯数据生成器，不处理 SSE 包装）
        :param user_message: 用户输入的消息
        :param code_gen_type: 代码生成类型
        :param app_id: 应用ID
        :param tools: 可选的工具列表，用于在生成代码时调用外部工具

        yields:
            dict: 数据块，格式为:
                  - {"d": "..."}          （token 流式输出）
        """
        pydantic_model = CodeFileType.get_cls_type(code_gen_type)
        memory_manager = get_chat_memory_manager()
        messages = memory_manager.get_llm_messages(
            app_id=app_id,
            extra_messages=[{"role": "user", "content": user_message}]
        )
        # 流式模式下不设置 response_format（结构化输出）
        # system_prompt 已经在 messages 中已经有了，这里手动添加一个空的 system_prompt 避免覆盖
        llm_client_builder = ChatClientBuilder().set_system_prompt("")
        if tools and len(tools) > 0:
            if isinstance(tools[0], str) and app_id:
                # 默认使用带上下文的工具调用，app_id 作为上下文
                llm_client_builder.add_tools_with_context_by_names(tools)
            elif isinstance(tools[0], str):
                llm_client_builder.add_tools_by_names(tools)
            else:
                llm_client_builder.add_tools(tools)
        llm_client = llm_client_builder.build()

        full_response_text = ""

        try:
            # 第一阶段：流式输出 token
            for chunk in llm_client.chat_stream(messages, tool_context={"app_id": app_id} if app_id else None):
                full_response_text += chunk.content
                # 只产出原始数据，不做 SSE 包装，这里会经过 stream_response 包装处理后返回给前端
                # 事实上 stream_response 包装也就是包装成了 SSE 格式数据流
                # chunk 类型是 StreamChunk，改成做相应的处理再返回给前端展示不同效果
                yield processed_chunk(chunk)
        except BusinessException:
            # 如果下游已经抛出了明确的业务异常，直接上抛
            raise
        except Exception as e:
            # AI 服务调用异常（网络、超时、服务不可用等）
            logger.error(f"AI流式生成调用失败: {e}")
            raise AIServiceError(f"AI服务调用失败: {e}") from e
        result = None
        # 第二阶段：解析 LLM 响应，优先使用自定义解析逻辑，兜底使用 JSON 解析
        try:
            result = pydantic_model.parse_response_from_llm(response=full_response_text)
        except Exception as e:
            # 尝试用正则兜底提取 JSON 字符串（AI 偶尔会在 JSON 外包裹解释性文本），解析失败仅记录异常日志，但是不抛出异常
            json_match = re.search(r'\{.*\}', full_response_text, re.DOTALL)
            if json_match:
                try:
                    result = pydantic_model.model_validate(json.loads(json_match.group()))
                except Exception as parse_err:      # 正则解析失败，直接返回原始响应交给解析器处理
                    logger.error(
                        f"AI 响应是JSON格式字符串，但是无法解析为{pydantic_model.__name__}: {parse_err}\n"
                        f"原始响应: {full_response_text}"
                    )
            else:
                logger.error(
                    f"AI 响应中未找到有效JSON结构，模型: {pydantic_model.__name__}\n"
                    f"原始响应: {full_response_text}"
                )
        # 第三阶段：保存文件并更新应用信息
        try:
            if result and isinstance(result, BaseCodeResult):
                if result.is_code_modified() and code_gen_type != CodeFileType.VUE_PROJECT:
                    # 非 Vue项目，保存代码文件，Vue项目由工具单独处理保存文件相关逻辑
                    saver = CodeFileSaverFactory.get_saver(code_gen_type)
                    saver.save_code_file(result, app_id)
                if result.is_name_modified():
                    update_app_svc(
                        app_id, get_app_creator_by_app_id(app_id),
                        AppUpdateRequest(app_name=result.app_name)
                    )
        except BusinessException:
            # 下游业务已抛出明确业务异常，直接上抛
            raise
        except Exception as e:
            logger.error(f"保存文件或更新应用信息失败: {e}")
            # 根据实际失败操作选择合适的错误码
            if isinstance(e, (OSError, IOError)):
                raise FileOperationError(f"文件写入失败: {e}") from e
            raise BusinessException(ErrorCode.INTERNAL_ERROR, f"保存结果失败: {e}") from e
