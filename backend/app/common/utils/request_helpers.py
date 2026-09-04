from flask import request

from backend.app.common.exceptions.error_codes import BusinessException, ErrorCode


def parse_pagination_args(max_per_page: int = 100) -> tuple[int, int]:
    """
    从 query string 解析分页参数并做范围校验

    Args:
        max_per_page: 每页最大数量上限，默认 100

    Returns:
        (page, per_page) 元组

    Raises:
        BusinessException: page < 1 或 per_page 超出 [1, max_per_page]
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    if page < 1:
        raise BusinessException(ErrorCode.INVALID_PARAMETER, "页码必须大于等于1")
    if per_page < 1 or per_page > max_per_page:
        raise BusinessException(
            ErrorCode.INVALID_PARAMETER,
            f"每页数量必须在1-{max_per_page}之间",
        )

    return page, per_page


def parse_json_body() -> dict:
    """
    获取并校验请求体 JSON

    Returns:
        解析后的 dict

    Raises:
        BusinessException: 请求体为空或不是合法 JSON
    """
    json_data = request.get_json(silent=True)
    if not json_data:
        raise BusinessException(ErrorCode.BAD_REQUEST, "请求体不能为空")
    return json_data
