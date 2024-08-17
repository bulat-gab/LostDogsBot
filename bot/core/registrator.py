from pyrogram import Client
from bot.config.config import settings
from bot.utils import logger
from bot.config.config import localization

async def register_sessions() -> None:
    API_ID = settings.API_ID
    API_HASH = settings.API_HASH

    if not API_ID or not API_HASH:
        raise ValueError(localization.get_message('registrator', 'api_not_found'))

    session_name = input(localization.get_message('registrator', 'enter_session_name'))

    if not session_name:
        return None

    session = Client(
        name=session_name,
        api_id=API_ID,
        api_hash=API_HASH,
        workdir="sessions/",
        lang_code=settings.LANGUAGE_CODE
    )

    async with session:
        user_data = await session.get_me()

    logger.success(localization.get_message('registrator', 'session_added').format(user_data.username, user_data.first_name, user_data.last_name))