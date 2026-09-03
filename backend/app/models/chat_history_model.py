from datetime import datetime
from backend.app.extensions.db_instance import db


class ChatHistory(db.Model):
    """对话历史模型"""
    __tablename__ = 'chat_history'

    id = db.Column(db.BigInteger, primary_key=True, comment='id')
    message = db.Column(db.Text, nullable=False, comment='消息')
    message_type = db.Column(db.String(32), comment='消息类型：user/ai')
    app_id = db.Column(db.BigInteger, db.ForeignKey('app.id', ondelete='CASCADE'), comment='应用id')
    user_id = db.Column(db.BigInteger, db.ForeignKey('user.id', ondelete='CASCADE'), comment='创建用户id')
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, comment='更新时间')
    is_delete = db.Column(db.SmallInteger, default=0, nullable=False, comment='是否删除')
    token_count = db.Column(db.Integer, default=0, nullable=False, comment='token数量')

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'message': self.message,
            'message_type': self.message_type,
            'app_id': self.app_id,
            'user_id': self.user_id,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'update_time': self.update_time.isoformat() if self.update_time else None,
            'is_delete': self.is_delete,
            'token_count': self.token_count,
        }

    def to_summary_dict(self):
        """转换为简要信息字典"""
        return {
            'id': self.id,
            'message': self.message,
            'message_type': self.message_type,
            'app_id': self.app_id,
            'user_id': self.user_id,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'token_count': self.token_count,
        }

    def __repr__(self):
        """字符串表示"""
        return f'<ChatHistory {self.id}>'
