from backend.app import create_app
from backend.app.config import get_config
from backend.app.extensions.db_instance import db

# 切换环境（命令行参数）：
#   python run.py           → prod（默认）
#   python run.py -dev      → dev
#   python run.py -test     → test
Config = get_config()

app = create_app(Config.as_flask_config())
db.init_app(app)

if __name__ == '__main__':
    app.run(
        debug=Config.DEBUG,
        use_reloader=False,     # 关闭热更新重载，利于边开发边调试
        host=Config.HOST,
        port=Config.PORT
    )
