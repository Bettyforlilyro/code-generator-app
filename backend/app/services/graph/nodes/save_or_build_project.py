"""
项目保存与构建节点
对应流程图中「生成项目结果（保存文件或者打包构建）」

复用已有的 CodeFileSaverFactory 策略模式：
- HTML / MULTI_FILE: 直接落盘到服务器目录
- VUE_PROJECT: Agent 已通过工具写入文件，此处触发异步 npm install + build
"""
import logging

from langchain_core.messages import AIMessage

from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.common.utils.code_file_saver import CodeFileSaverFactory
from backend.app.schemas.ai_generate_results import BaseCodeResult
from backend.app.services.graph.state.workflow_state import WorkflowState

logger = logging.getLogger(__name__)


def save_or_build_project_node(state: WorkflowState) -> dict:
    """
    保存生成的代码文件 / 触发构建

    Args:
        state: 当前工作流状态

    Returns:
        dict: 要更新到 state 中的字段（code_save_path / build_success_path）
    """
    code_gen_type = state.get("code_gen_type", CodeFileType.HTML.value)
    app_id = state.get("app_id")
    generate_output = state.get("generate_output", "")

    if not app_id:
        logger.warning("[save_or_build] state 中缺少 app_id，无法保存文件")
        return {
            "current_node": "save_or_build",
            "error_info": "缺少 app_id，无法保存",
        }

    try:
        # HTML/MULTI_FILE：直接落盘到服务器目录（generate_output 已经是结构化 BaseCodeResult 类型）
        # VUE_PROJECT 在 save_code_file 中已实现将保存的所有文件启动异步构建流程，因此统一调用即可
        ai_full_message = ""
        for message in reversed(state.get("messages", [])):
            if isinstance(message, AIMessage) and message.content:
                ai_full_message = message.content
                break
        if isinstance(generate_output, BaseCodeResult) and generate_output.is_code_modified(ai_full_message):
            saver = CodeFileSaverFactory.get_saver(code_gen_type)
            save_path = saver.save_code_file(generate_output, app_id)
            logger.info(f"[save_or_build] {code_gen_type} 保存成功: {save_path}")

            return {
                "current_node": "save_or_build",
                "code_save_path": save_path,
            }
    except Exception as e:
        logger.error(f"[save_or_build] 保存/构建失败: {e}", exc_info=True)
        return {
            "current_node": "save_or_build",
            "error_info": f"保存/构建失败: {e}",
        }
