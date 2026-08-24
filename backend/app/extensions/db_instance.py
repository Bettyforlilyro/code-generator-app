"""
Flask扩展实例管理模块

将所有Flask扩展实例集中管理，避免循环导入问题
"""
from flask_sqlalchemy import SQLAlchemy

# 创建数据库实例（不绑定任何app）
db = SQLAlchemy()
