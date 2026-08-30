from datetime import datetime
from backend.app.extensions.db_instance import db


class AppModel(db.Model):
    """应用模型（AI生成的网页应用）"""
    __tablename__ = 'app'

    id = db.Column(db.BigInteger, primary_key=True, comment='id')
    app_name = db.Column(db.String(256), nullable=False, comment='应用名称')
    app_coverage = db.Column(db.String(1024), comment='应用封面图标URL')
    init_prompt = db.Column(db.Text, comment='应用初始化的用户Prompt')
    code_gen_type = db.Column(db.String(64), comment='代码生成类型：枚举值（如html/css/js/multi_file等）')
    deploy_key = db.Column(db.String(64), unique=True, comment='应用部署唯一标识ID')
    deploy_time = db.Column(db.DateTime, comment='部署时间：未部署时为NULL')
    priority = db.Column(db.Integer, default=0, nullable=False, comment='首页展示优先级')
    user_id = db.Column(db.BigInteger, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, comment='创建用户ID（关联user表id）')
    edit_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, comment='编辑时间：业务代码手动更新')
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment='更新时间：数据库自动更新')
    is_delete = db.Column(db.SmallInteger, default=0, nullable=False, comment='是否删除：0-正常，1-已删除')

    def to_dict(self, include_prompt=True, user_name=None, user=None):
        """转换为字典"""
        result = {
            'id': self.id,
            'app_name': self.app_name,
            'app_coverage': self.app_coverage,
            'code_gen_type': self.code_gen_type,
            'deploy_key': self.deploy_key,
            'deploy_time': self.deploy_time.isoformat() if self.deploy_time else None,
            'priority': self.priority,
            'user_id': self.user_id,
            'user_name': user_name,
            'user': user,
            'edit_time': self.edit_time.isoformat() if self.edit_time else None,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'update_time': self.update_time.isoformat() if self.update_time else None,
        }
        if include_prompt:
            result['init_prompt'] = self.init_prompt
        return result

    def to_summary_dict(self, user_name=None, user=None):
        """转换为简要信息字典（列表展示用）"""
        return {
            'id': self.id,
            'app_name': self.app_name,
            'app_coverage': self.app_coverage,
            'code_gen_type': self.code_gen_type,
            'deploy_key': self.deploy_key,
            'deploy_time': self.deploy_time.isoformat() if self.deploy_time else None,
            'priority': self.priority,
            'user_id': self.user_id,
            'user_name': user_name,
            'user': user,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'update_time': self.update_time.isoformat() if self.update_time else None
        }

    def __repr__(self):
        """字符串表示"""
        return f'<App {self.app_name}>'