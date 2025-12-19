import logging
from pathlib import Path

from pydantic import BaseSettings, HttpUrl


class Settings(BaseSettings):
    receiver_url: HttpUrl
    receiver_token: str
    poller_active: bool = False
    debug: bool = False
    poller_connection_timeout: float = 1.5

    class Config:
        # env_file = '.env'
        env_file = f'{Path(__file__).resolve().parent.parent}/.env'
        env_file_encoding = 'utf-8'


settings = Settings()
logging_level = logging.DEBUG if settings.debug else logging.INFO


def configure_logging(level=logging_level):
    logging.basicConfig(
        level=level,
        datefmt='%Y-%m-%d %H:%M:%S',
        format='[%(asctime)s.%(msecs)03d] %(module)10s:%(lineno)-3d '
               '%(levelname)-7s - %(message)s',
    )
