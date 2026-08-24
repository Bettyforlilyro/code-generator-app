import os

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

# 从环境变量获取配置
config = {
    'DEBUG': os.getenv('FLASK_DEBUG', 'True').lower() == 'true',
    'HOST': os.getenv('FLASK_HOST', '0.0.0.0'),
    'PORT': int(os.getenv('FLASK_PORT', '5000')),
    'SECRET_KEY': os.getenv('SECRET_KEY'),
    'REFRESH_SECRET_KEY': os.getenv('REFRESH_SECRET_KEY'),
    'SQLALCHEMY_DATABASE_URI': f'postgresql://{db_user}:{db_password}@{db_host}:{db_post}/{db_name}',
    'SQLALCHEMY_TRACK_MODIFICATIONS': False
}

app = create_app(config)
db.init_app(app)

if __name__ == '__main__':
    app.run(
        debug=config['DEBUG'],
        host=config['HOST'],
        port=config['PORT']
    )
