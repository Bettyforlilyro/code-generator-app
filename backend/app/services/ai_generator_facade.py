import json
import logging
import re

from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.common.exceptions.error_codes import (
    ErrorCode, AIServiceError, AIResponseParseError, FileOperationError, BusinessException,
)
from backend.app.common.utils.code_file_saver import CodeFileSaverFactory
from backend.app.schemas.requests.app_management_request import AppUpdateRequest
from backend.app.services.ai_common.chat_memory import get_chat_memory_manager
from backend.app.services.ai_common.llm_client import ChatClientBuilder
from backend.app.services.app_service import update_app_svc, get_app_creator_by_app_id

logger = logging.getLogger(__name__)


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
    def generate_code_and_save_file_streaming(user_message: str, code_gen_type: CodeFileType, app_id: int):
        """
        流式生成代码并保存文件的生成器（纯数据生成器，不处理 SSE 包装）

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
        # 关键区别：流式模式下不设置 response_format（结构化输出）
        # 只设置 system_prompt，让 AI 按 prompt 要求输出 JSON 格式文本
        llm_client = (ChatClientBuilder()
                      .set_system_prompt("")    # system_prompt已经存到数据库中了，从messages中已经有了
                      .build())

        full_response = ""

        try:
            # 第一阶段：流式输出 token
            for chunk in llm_client.chat_stream(messages):
                full_response += chunk.content
                # 只产出原始数据，不做 SSE 包装
                yield {"d": chunk.content}
        except BusinessException:
            # 如果下游已经抛出了明确的业务异常，直接上抛
            raise
        except Exception as e:
            # AI 服务调用异常（网络、超时、服务不可用等）
            logger.error(f"AI流式生成调用失败: {e}")
            raise AIServiceError(f"AI服务调用失败: {e}") from e

        # 第二阶段：解析完整 JSON 响应，正常情况下系统 prompt 只允许 AI 返回 JSON 格式的文本
        try:
            result = pydantic_model.model_validate_json(full_response)
        except Exception:
            # 尝试用正则兜底提取 JSON 字符串（AI 偶尔会在 JSON 外包裹解释性文本）
            json_match = re.search(r'\{.*\}', full_response, re.DOTALL)
            if json_match:
                try:
                    result = pydantic_model.model_validate(json.loads(json_match.group()))
                except Exception as parse_err:
                    logger.error(
                        f"正则兜底后仍无法解析AI响应为{pydantic_model.__name__}: {parse_err}\n"
                        f"原始响应: {full_response}"
                    )
                    raise AIResponseParseError(
                        f"AI响应格式错误，无法解析为{pydantic_model.__name__}"
                    ) from parse_err
            else:
                logger.error(
                    f"AI响应中未找到有效JSON，模型: {pydantic_model.__name__}\n"
                    f"原始响应: {full_response}"
                )
                raise AIResponseParseError(
                    f"AI响应中未找到有效JSON结构，无法解析为{pydantic_model.__name__}"
                )

        # 第三阶段：保存文件并更新应用信息
        try:
            if result.is_code_modified():
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