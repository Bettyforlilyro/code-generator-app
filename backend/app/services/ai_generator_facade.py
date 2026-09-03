import logging

from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.common.utils.code_file_saver import CodeFileSaverFactory
from backend.app.extensions.db_instance import db
from backend.app.models.app_model import AppModel
from backend.app.services.ai_common.LLM_Client import ChatClientBuilder
from backend.app.services.ai_common.chat_memory import get_chat_memory_manager


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

            # 第二阶段：解析完整 JSON 响应，正常情况下系统prompt只允许AI返回JSON格式的文本
            try:
                result = pydantic_model.model_validate_json(full_response)
            except Exception as e:
                import re, json
                json_match = re.search(r'\{.*\}', full_response, re.DOTALL)
                if json_match:
                    result = pydantic_model.model_validate(
                        json.loads(json_match.group())
                    )
                else:
                    raise ValueError(f"无法解析AI响应为{pydantic_model.__name__}:\n原始响应: {full_response}, 错误信息: {str(e)}")

            # 第三阶段：保存文件
            if result.is_code_modified():
                saver = CodeFileSaverFactory.get_saver(code_gen_type)
                saver.save_code_file(result, app_id)
            # 第四阶段，更新应用名称
            try:
                if result.is_name_modified():
                    app = AppModel.query.filter_by(id=app_id).first()
                    app.app_name = result.app_name
                    db.session.commit()
            except Exception as e:
                logging.warning(f"更新应用名称失败，应用ID: {app_id}，错误信息: {str(e)}")

        except Exception as e:
            # 产出错误事件数据
            yield {
                "d": str(e)
            }

