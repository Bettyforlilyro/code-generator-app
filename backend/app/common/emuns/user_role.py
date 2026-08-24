from enum import Enum


class UserRole(str, Enum):
    """用户角色枚举"""

    ADMIN = "admin"
    USER = "user"

    @classmethod
    def get_all_roles(cls):
        """获取所有角色列表"""
        return [role.value for role in cls]

    @classmethod
    def is_valid_role(cls, role: str) -> bool:
        """验证角色是否有效"""
        return role in cls.get_all_roles()

    def __str__(self):
        return self.value

