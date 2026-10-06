"""
Flask扩展实例管理模块

将所有Flask扩展实例集中管理，避免循环导入问题
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# 创建数据库实例（不绑定任何app）
db = SQLAlchemy()
# 创建迁移实例（不绑定任何app）
migrate = Migrate()
