import os

import pytest
from dotenv import load_dotenv

from backend.app import create_app
from backend.app.extensions.db_instance import db

# 加载 .env 文件中的环境变量
load_dotenv()

db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_post = os.getenv('DB_PORT')
db_name = os.getenv('DB_NAME')


@pytest.fixture
def app():
    """创建测试用的Flask应用"""
    test_config = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'postgresql://{db_user}:{db_password}@{db_host}:{db_post}/{db_name}',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False
    }
    app = create_app(test_config)
    db.init_app(app)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """创建CLI测试运行器"""
    return app.test_cli_runner()
