# ==================== LLM JSON 回复解析工具 ====================
# 独立于 ChatClient 的纯工具方法，输入 LLM response 文本 + Pydantic 模型，
# 四层防御策略从混乱的 prose/markdown/嵌套包裹中精准提取并修复 JSON，
# 最终返回通过 pydantic 验证的结构化结果。
# 被 ChatClient.chat_structured() 调用，也可单独使用。
import logging
import re

from json_repair import json_repair

_logger = logging.getLogger(__name__)


def _extract_balanced_json_objects(text: str) -> list[str]:
    """
    括号平衡提取器：找出 text 中所有 "{...}" 完全平衡的子串。

    关键边界保护：
      1. 只在 depth>0 时才识别双引号（prose 里的 "hello" 不干扰）
      2. 只在 in_string=True 时才处理转义（JSON 字符串内的 \\ \" 等）

    Returns:
        list[str]: 所有平衡的 JSON 候选子串（不保证是有效 JSON，调用方需再验证）
    """
    results: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escape_next = False

    for i, ch in enumerate(text):
        if in_string:
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"':
                in_string = False
            continue
        if depth > 0 and ch == '"':
            in_string = True
            continue
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    results.append(text[start:i + 1])
                    start = -1
    return results


def _iter_all_dicts(obj) -> list[dict]:
    """
    从一个（可能嵌套的）JSON 对象中，递归提取所有层级的 dict 作为候选。
    解决 LLM 外层套壳 {"data": {"name":"Bob"}, "status":"ok"} 时内层 dict 也需要验证的问题。
    """
    results: list[dict] = []

    def walk(o):
        if isinstance(o, dict):
            results.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for item in o:
                walk(item)
    walk(obj)
    return results


def _normalize_json_repair_result(result) -> list[dict]:
    """
    json_repair.loads / repair_json(return_objects=True) 返回类型不稳定：
      - 单个 JSON → dict
      - 多候选/修复失败混合 → list[dict|str|...]
      - 完全不是 JSON → str 或 None
    统一成 list[dict]，过滤掉非 dict 垃圾值。
    """
    if result is None:
        return []
    if isinstance(result, dict):
        return [result]
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    return []


def parse_llm_json_response(response: str, pydantic_model):
    """
    从 LLM 的自由文本回复中，用四层防御策略精准提取 JSON 并解析为 Pydantic 模型。

    四层防御（按效率从高到低，先尝试快速解析，命中即返回）：
      Layer1  model_validate_json              标准路径（纯 JSON 最快）
      Layer2  json_repair 整体解析             跳过 prose + 修复非法转义 + 嵌套遍历
      Layer3  括号平衡精准切分 + json_repair    手动定位边界再逐个修复
      Layer4  正则非贪婪 + json_repair          终极兜底

    Args:
        response: LLM 的完整回复文本（可能含 prose/markdown/多 JSON 混合）
        pydantic_model: 用于验证的 Pydantic 模型类

    Returns:
        通过验证的 Pydantic 模型实例

    Raises:
        ValueError: 四层防御全部失败时
    """
    model_name = pydantic_model.__name__

    # ---- Layer1: 标准 Pydantic JSON 解析（最快，LLM 完全听话时） ----
    try:
        return pydantic_model.model_validate_json(response)
    except Exception as e:
        _logger.debug(f"[parse_llm_json_response][{model_name}] Layer1 标准JSON解析失败，错误信息: {e}")

    # ---- Layer2: json_repair 整体解析 + 所有嵌套层验证 ----
    try:
        for obj in _normalize_json_repair_result(json_repair.loads(response)):
            for candidate_dict in _iter_all_dicts(obj):
                try:
                    return pydantic_model.model_validate(candidate_dict)
                except Exception:
                    continue
    except Exception as e:
        _logger.debug(f"[parse_llm_json_response][{model_name}] Layer2 json_repair解析失败，错误信息: {e}")

    # ---- Layer3: 括号平衡精准切分 + json_repair + 所有嵌套层验证 ----
    candidates = _extract_balanced_json_objects(response)
    for idx, candidate in enumerate(candidates):
        try:
            for obj in _normalize_json_repair_result(json_repair.loads(candidate)):
                for candidate_dict in _iter_all_dicts(obj):
                    try:
                        return pydantic_model.model_validate(candidate_dict)
                    except Exception:
                        continue
        except Exception as e:
            _logger.debug(f"[parse_llm_json_response][{model_name}] Layer3 候选#{idx+1}\n{candidate} 解析失败，错误信息: {e}")

    # ---- Layer4: 正则非贪婪兜底 ----
    try:
        for match in re.finditer(r'\{[^{}]*\}', response):
            try:
                for obj in _normalize_json_repair_result(
                    json_repair.loads(match.group())
                ):
                    for candidate_dict in _iter_all_dicts(obj):
                        try:
                            return pydantic_model.model_validate(candidate_dict)
                        except Exception:
                            continue
            except Exception:
                continue
    except Exception as e:
        _logger.debug(f"[parse_llm_json_response][{model_name}] Layer4 正则匹配解析失败，错误信息: {e}")

    # ---- 全层失败 ----
    _logger.error(
        f"[parse_llm_json_response][{model_name}] 四层解析全部失败！"
        f"response长度={len(response)}, 前100字={response[:100]}"
    )
    raise ValueError(
        f"无法将AI响应解析为 {model_name}\n"
        f"原始响应: {response}"
    )
