"""
应用启动入口

环境切换（命令行参数）：
    python run.py           → prod（默认）
    python run.py -dev      → dev
    python run.py -test     → test
"""
from backend.app import create_app
from backend.app.config import get_config

app = create_app(get_config().as_flask_config())

if __name__ == '__main__':
    cfg = get_config()
    app.run(
        debug=cfg.DEBUG,
        use_reloader=False,  # 关闭热更新重载，利于边开发边调试
        host=cfg.HOST,
        port=cfg.PORT,
    )
