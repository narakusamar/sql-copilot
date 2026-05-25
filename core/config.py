import os
from pathlib import Path
from dotenv import load_dotenv

_CONFIG_DIR = Path(__file__).parent


def _load_env():
    load_dotenv(_CONFIG_DIR / "config.env", override=True)


_load_env()


class Config:
    API_KEY: str = ""
    BASE_URL: str = ""
    MODEL: str = ""
    MAX_RETRIES: int = 3
    DB_TYPE: str = "sqlite"
    DB_PATH: str = ""
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "superstore"
    HF_ENDPOINT: str = "https://hf-mirror.com"

    @classmethod
    def reload(cls):
        """重新加载配置，用于 UI 修改 config.env 后热更新"""
        _load_env()
        cls.API_KEY = os.getenv("API_KEY", cls.API_KEY)
        cls.BASE_URL = os.getenv("BASE_URL", cls.BASE_URL)
        cls.MODEL = os.getenv("MODEL", cls.MODEL)
        cls.MAX_RETRIES = int(os.getenv("MAX_RETRIES", str(cls.MAX_RETRIES)))
        cls.DB_TYPE = os.getenv("DB_TYPE", cls.DB_TYPE)
        cls.DB_PATH = os.getenv("DB_PATH", cls.DB_PATH)
        cls.DB_HOST = os.getenv("DB_HOST", cls.DB_HOST)
        cls.DB_PORT = int(os.getenv("DB_PORT", str(cls.DB_PORT)))
        cls.DB_USER = os.getenv("DB_USER", cls.DB_USER)
        cls.DB_PASSWORD = os.getenv("DB_PASSWORD", cls.DB_PASSWORD)
        cls.DB_NAME = os.getenv("DB_NAME", cls.DB_NAME)
        cls.HF_ENDPOINT = os.getenv("HF_ENDPOINT", cls.HF_ENDPOINT)


# 首次加载
Config.reload()
