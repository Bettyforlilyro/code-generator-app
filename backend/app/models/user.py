from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from backend.app.extensions.db_instance import db


class User(db.Model):
    """用户模型"""
    __tablename__ = 'user'

    id = db.Column(db.BigInteger, primary_key=True, comment='id')
    user_account = db.Column(db.String(256), unique=True, nullable=False, index=True, comment='账号')
    user_password = db.Column(db.String(512), nullable=False, comment='密码')
    user_name = db.Column(db.String(256), index=True, comment='用户昵称')
    user_avatar = db.Column(db.String(1024), comment='用户头像')
    user_profile = db.Column(db.String(512), comment='用户简介')
    user_role = db.Column(db.String(256), default='user', nullable=False, comment='用户角色：user/admin')
    edit_time = db.Column(db.DateTime, default=datetime.utcnow, comment='编辑时间')
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment='更新时间')
    is_delete = db.Column(db.SmallInteger, default=0, nullable=False, comment='是否删除')

    def set_password(self, password):
        """设置加密密码"""
        self.user_password = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.user_password, password)

    def to_dict(self):
        """转换为字典（不包含密码和敏感信息）"""
        return {
            'id': self.id,
            'user_account': self.user_account,
            'user_name': self.user_name,
            'user_avatar': self.user_avatar,
            'user_profile': self.user_profile,
            'user_role': self.user_role,
            'edit_time': self.edit_time.isoformat() if self.edit_time else None,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'update_time': self.update_time.isoformat() if self.update_time else None,
            'is_delete': self.is_delete
        }

    def to_summary_dict(self):
        """转换为简要信息字典（不包含密码和敏感信息）"""
        return {
            'id': self.id,
            'user_account': self.user_account,
            'user_name': self.user_name,
            'user_avatar': self.user_avatar,
            'user_profile': self.user_profile,
            'user_role': self.user_role,
        }

    def __repr__(self):
        """字符串表示"""
        return f'<User {self.user_account}>'
