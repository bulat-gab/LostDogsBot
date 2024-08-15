from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str
    
    BOT_TOKEN: str = ""
    ADMIN_UID: int = 0
    
    RANDOM_CARD: bool = False
    AUTO_TASK: bool = True
    
    SLEEP_TIME: list[int] = [1800, 3600]
    USE_RANDOM_DELAY_IN_RUN: bool = False
    RANDOM_DELAY_IN_RUN: list[int] = [0, 15]

    USE_PROXY_FROM_FILE: bool = False


settings = Settings()
