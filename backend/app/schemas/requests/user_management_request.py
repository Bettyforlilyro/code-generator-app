from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional
import re

from backend.app.common.exceptions.error_codes import BusinessException, ErrorCode


class UserRegisterRequest(BaseModel):
    """用户注册请求模型"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_name": "张三",
                "user_password": "Password123!",
                "confirm_password": "Password123!"
            }
        }
    )

    user_name: str = Field(
        ...,
        max_length=256,
        description="用户昵称",
        examples=["张三"]
    )
    user_password: str = Field(
        ...,
        max_length=512,
        description="用户密码",
        examples=["Password123!"]
    )
    confirm_password: str = Field(
        ...,
        max_length=512,
        description="确认密码",
        examples=["Password123!"]
    )

    @field_validator('user_password')
    @classmethod
    def validate_user_password(cls, v: str) -> str:
        """验证密码强度"""
        if len(v) < 6:
            raise BusinessException(ErrorCode.INVALID_PARAMETER, "密码长度不能小于6个字符")
        return v

    @field_validator('confirm_password')
    @classmethod
    def validate_confirm_password(cls, v: str, info) -> str:
        """验证确认密码与密码一致"""
        values = info.data
        if 'user_password' in values and v != values['user_password']:
            raise BusinessException(ErrorCode.INVALID_PARAMETER, "两次输入的密码不一致")
        return v


class UserLoginRequest(BaseModel):
    """用户登录请求模型"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_name": "张三",
                "user_password": "Password123!"
            }
        }
    )

    user_name: str = Field(
        ...,
        max_length=256,
        description="用户昵称",
        examples=["张三"]
    )
    user_password: str = Field(
        ...,
        max_length=512,
        description="用户密码",
        examples=["Password123!"]
    )


class UserUpdateRequest(BaseModel):
    """用户信息更新请求模型"""
    user_name: str = Field(
        None,
        min_length=1,
        max_length=50,
        description="用户昵称"
    )
    user_avatar: str = Field(
        None,
        max_length=1024,
        description="用户头像URL"
    )
    user_profile: str = Field(
        None,
        max_length=512,
        description="用户简介"
    )
