from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str
    
    BOT_TOKEN: str = None
    ADMIN_UID: int = 0
    
    RANDOM_CARD: bool = False
    AUTO_TASK: bool = True

    USE_PROXY_FROM_FILE: bool = False


settings = Settings()
