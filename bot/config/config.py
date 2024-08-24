from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import os


class Localization:
    def __init__(self):
        self._messages = self._load_language_file()

    def _load_language_file(self):
        language_code = settings.LANGUAGE_CODE
        file_path = os.path.join('locales', f'locales_{language_code}.json')
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)

    def get_message(self, *keys, **kwargs):
        try:
            result = self._messages
            for key in keys:
                if isinstance(result, dict):
                    result = result[key]
                else:
                    raise KeyError(f"Invalid key path: {'.'.join(map(str, keys))}")
            
            if isinstance(result, str):
                return result.format(**kwargs) if kwargs else result
            else:
                raise ValueError(f"Expected string, got {type(result)}")
        except (KeyError, ValueError):
            return f"Missing localization: {'.'.join(map(str, keys))}"

    def get_button_text(self, button_key):
        return self.get_message('telegram_bot', 'buttons', button_key)

    def get_task_type(self, task_type):
        return self.get_message('telegram_bot', 'task_type', task_type)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str
    
    BOT_TOKEN: str = ""
    ADMIN_UID: int = 0
    LANGUAGE_CODE: str = "ru"
    REF_ID: str = "ref-u_339631649__s_650113"
    RANDOM_CARD: bool = False
    AUTO_TASK: bool = True
    FAKE_USERAGENT: bool = True
    
    SLEEP_TIME: list[int] = [1800, 3600]
    USE_RANDOM_DELAY_IN_RUN: bool = False
    RANDOM_DELAY_IN_RUN: list[int] = [0, 15]

    USE_PROXY_FROM_FILE: bool = False


settings = Settings()
localization = Localization()