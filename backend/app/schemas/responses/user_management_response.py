from typing import Optional, Any
from pydantic import BaseModel, Field


class UserRegisterResponse(BaseModel):
    """用户注册响应"""
    id: int
    user_account: str
    user_name: str
    user_role: str
    token: str = ""


class UserLoginResponse(BaseModel):
    """用户登录响应"""
    id: int
    user_account: str
    user_name: str
    user_avatar: Optional[str] = None
    user_profile: Optional[str] = None
    user_role: str
    token: str = ""

