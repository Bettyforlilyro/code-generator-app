import time
import uuid


def generate_user_account() -> str:
    """
    生成唯一的用户账号

    规则：时间戳后6位 + 随机4位字符

    Returns:
        唯一的用户账号字符串
    """
    timestamp_suffix = str(int(time.time() * 1000))[-6:]
    random_suffix = str(uuid.uuid4()).replace('-', '')[:4]
    return f"{timestamp_suffix}{random_suffix}"
