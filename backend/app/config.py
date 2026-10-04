"""
配置管理中心类

设计原则：
    1. 外层通过 get_config() 拿配置
    2. load_dotenv() 只在这里执行一次，根据命令行参数加载相应环境配置.env{env_type}
    3. 当前未实现环境变量覆盖和扩展，所有配置类默认都继承 Config 基类

环境配置来源：项目根目录参考 .env.example
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def load_env_sys_args() -> str:
    """
    解析命令行的环境参数
    """
    for arg in sys.argv[1:]:
        arg_lower = arg.lower()
        if arg_lower in ('-dev', '--dev'):
            return 'dev'
        if arg_lower in ('-test', '--test'):
            return 'test'
        if arg_lower in ('-prod', '--prod'):
            return 'prod'
    return 'prod'


def load_env_file(app_env: str | None = None) -> None:
    """
    查找顺序：优先根据命令行参数加载对应配置，找不到则加载默认文件 .env
    """
    if not app_env:
        app_env = 'prod'

    project_root = Path(__file__).resolve().parent.parent.parent    # 项目根目录

    env_specific_file = project_root / f'.env.{app_env}'
    default_file = project_root / '.env'

    if env_specific_file.exists():
        load_dotenv(env_specific_file, override=True)
    elif default_file.exists():
        load_dotenv(default_file)
    # 两个都不存在就纯靠系统环境变量


# 模块 import 时立即解析命令行参数并加载对应 .env 文件，必须在 Config 类定义之前完成
_APP_ENV = load_env_sys_args()
load_env_file(_APP_ENV)


class Config:
    """
    所有环境变量在这里统一声明 + 提供默认值。
    未来如需区分 dev/prod/test，可继承此类覆盖属性（暂不实现）。
    """

    # Flask 应用基础
    DEBUG: bool = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    HOST: str = os.getenv('FLASK_HOST', '0.0.0.0')
    PORT: int = int(os.getenv('FLASK_PORT', '5000'))

    # JWT 签名密钥
    SECRET_KEY: str = os.getenv(
        'SECRET_KEY', 'dev-secret-key-change-in-production'
    )
    REFRESH_SECRET_KEY: str = os.getenv(
        'REFRESH_SECRET_KEY', 'dev-refresh-secret-key-change-in-production'
    )

    # PostgreSQL 数据库
    DB_USER: str = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD: str = os.getenv('DB_PASSWORD', '')
    DB_HOST: str = os.getenv('DB_HOST', 'localhost')
    DB_PORT: str = os.getenv('DB_PORT', '5432')
    DB_NAME: str = os.getenv('DB_NAME', '')

    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    @classmethod
    def get_database_uri(cls) -> str:
        return (
            f'postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}'
            f'@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}'
        )

    # 通义千问 LLM —— 默认/测试模型（低优先级，可缺省）
    DEFAULT_AND_TEST_MODEL_API_KEY: str = os.getenv(
        'DEFAULT_AND_TEST_MODEL_API_KEY', ''
    )
    DEFAULT_AND_TEST_MODEL_OPENAI_COMPATIBLE_BASE_URL: str = os.getenv(
        'DEFAULT_AND_TEST_MODEL_OPENAI_COMPATIBLE_BASE_URL', ''
    )
    DEFAULT_AND_TEST_MODEL: str = os.getenv('DEFAULT_AND_TEST_MODEL', 'qwen-plus')

    # 通义千问 LLM —— 主生产模型（代码生成核心）
    MODEL_OPENAI_COMPATIBLE_BASE_URL: str = os.getenv(
        'MODEL_OPENAI_COMPATIBLE_BASE_URL', ''
    )
    MODEL_API_KEY: str = os.getenv('MODEL_API_KEY', '')
    # qwen-flash —— 响应快效果差，适合路由判断
    ROUTER_MODEL_OPENAI_COMPATIBLE: str = os.getenv(
        'ROUTER_MODEL_OPENAI_COMPATIBLE', 'qwen-flash'
    )
    # qwen3-max-preview / qwen-max —— 响应慢效果好，适合生成代码
    CODE_GENERATOR_MODEL_EASY_OPENAI_COMPATIBLE: str = os.getenv(
        'CODE_GENERATOR_MODEL_EASY_OPENAI_COMPATIBLE', 'qwen3-max-preview'
    )
    CODE_GENERATOR_MODEL_COMPLEX_OPENAI_COMPATIBLE: str = os.getenv(
        'CODE_GENERATOR_MODEL_COMPLEX_OPENAI_COMPATIBLE', 'qwen-max'
    )

    # 通义千问 LLM —— 文生图（Logo 生成）
    TONGYI_DASHSCOPE_BASE_URL: str = os.getenv('TONGYI_DASHSCOPE_BASE_URL', '')
    TONGYI_IMAGE_GEN_MODEL: str = os.getenv(
        'TONGYI_IMAGE_GEN_MODEL', 'qwen-image-3.0'
    )
    TONGYI_IMAGE_GEN_API_KEY: str = os.getenv('TONGYI_IMAGE_GEN_API_KEY', '')

    # Pexels 图片搜索
    PEXELS_API_KEY: str = os.getenv('PEXELS_API_KEY', '')

    # 盒子随机图（注册头像，不重要）
    HZI_DEV_ID: str = os.getenv('HZI_DEV_ID', '')
    HZI_KEY: str = os.getenv('HZI_KEY', '')

    # 图床服务（本地 easyimages）
    IMAGE_BED_URL: str = os.getenv('IMAGE_BED_URL', '')
    IMAGE_BED_TOKEN: str = os.getenv('IMAGE_BED_TOKEN', '')

    # 本地文件系统路径
    NGINX_PATH: str = os.getenv('NGINX_PATH', r'D:\Nginx\nginx.exe')
    GENERATE_ROOT: str = os.getenv('GENERATE_ROOT',
                                   os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "generated_apps"))
    DEFAULT_ROOT: str = os.getenv('DEFAULT_ROOT', os.path.join(GENERATE_ROOT, "deployed"))
    SCREENSHOT_DIR: str = os.getenv('SCREENSHOT_DIR', os.path.join(GENERATE_ROOT, "screenshots"))

    @classmethod
    def as_flask_config(cls) -> dict:
        """转换为 Flask 可接受的配置 dict（仅 Flask/SQLAlchemy 运行所需）

        LLM 密钥、图床路径等业务配置不放进 Flask config，
        那些通过 Config.XXX 直接访问类属性即可。
        """
        return {
            'DEBUG': cls.DEBUG,
            'HOST': cls.HOST,
            'PORT': cls.PORT,
            'SECRET_KEY': cls.SECRET_KEY,
            'REFRESH_SECRET_KEY': cls.REFRESH_SECRET_KEY,
            'SQLALCHEMY_DATABASE_URI': cls.get_database_uri(),
            'SQLALCHEMY_TRACK_MODIFICATIONS': cls.SQLALCHEMY_TRACK_MODIFICATIONS,
        }


# 环境专属 Config 子类（预留扩展点，目前继承基类全部属性）
class DevConfig(Config):
    """开发环境配置（预留扩展）"""
    pass


class ProdConfig(Config):
    """生产环境配置（预留扩展）"""
    pass


class TestConfig(Config):
    """测试环境配置（预留扩展）"""
    pass


# 工厂函数 —— 返回当前环境的 Config 子类
def get_config() -> type[Config]:
    config_map = {
        'dev': DevConfig,
        'prod': ProdConfig,
        'test': TestConfig,
    }
    return config_map.get(_APP_ENV, ProdConfig)
