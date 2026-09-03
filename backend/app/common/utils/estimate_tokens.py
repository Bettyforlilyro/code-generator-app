from loguru import logger
import tiktoken


def estimate_tokens(text: str) -> int:
    """
    估算一段文本的 token 数

    优先使用 tiktoken（若已安装），否则按中文 1 字 ≈ 1.5 token、英文 1 词 ≈ 1 token 进行粗略估算。
    估算结果偏保守（宁多勿少）。
    """
    if not text:
        return 0

    # 方案一：使用 tiktoken（推荐，准确）
    try:
        # cl100k_base 是 GPT-4 / 通义 qwen 通用的编码
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"tiktoken 估算失败，降级为字符估算: {e}")

    # 方案二：粗略估算（兜底）
    # 中文每字约 1.5 token，英文每 4 字符约 1 token
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars / 4)
