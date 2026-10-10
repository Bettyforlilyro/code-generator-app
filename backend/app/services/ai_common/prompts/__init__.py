from backend.app.common.enums import CodeFileType
from backend.app.schemas.responses import HtmlCodeResult, MultiFileCodeResult, VueProjectFileCodeResult
from .generate_routing_prompt import CODE_GENERATE_ROUTING_SYSTEM_PROMPT
from .html_prompt import CODE_GENERATE_HTML_SYSTEM_PROMPT
from .image_prompts import IMAGE_COLLECTION_SYSTEM_PROMPT, IMAGE_COLLECTION_PLAN_SYSTEM_PROMPT
from .multi_file_prompt import CODE_GENERATE_MULTI_FILE_SYSTEM_PROMPT
from .quality_check_prompt import CODE_QUALITY_CHECK_SYSTEM_PROMPT
from .vue_project_prompt import CODE_GENERATE_VUE_PROJECT_SYSTEM_PROMPT

SYSTEM_PROMPT_MAP = {
    CodeFileType.HTML.value: CODE_GENERATE_HTML_SYSTEM_PROMPT,
    CodeFileType.MULTI_FILE.value: CODE_GENERATE_MULTI_FILE_SYSTEM_PROMPT,
    CodeFileType.VUE_PROJECT.value: CODE_GENERATE_VUE_PROJECT_SYSTEM_PROMPT,
}

RESPONSE_CLASS_MAP = {
    CodeFileType.HTML.value: HtmlCodeResult,
    CodeFileType.MULTI_FILE.value: MultiFileCodeResult,
    CodeFileType.VUE_PROJECT.value: VueProjectFileCodeResult,
}


def get_system_prompt(file_type: str) -> str | None:
    """根据代码文件类型获取对应的系统提示词"""
    return SYSTEM_PROMPT_MAP.get(file_type)


def get_response_cls(file_type: str):
    """根据代码文件类型获取对应的 Pydantic 响应模型类"""
    return RESPONSE_CLASS_MAP.get(file_type)
