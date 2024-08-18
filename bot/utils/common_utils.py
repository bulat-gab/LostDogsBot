import glob
import os

from ..config import *
from . import logger
from pyrogram import Client
from better_proxy import Proxy

global tg_clients

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

def get_session_names() -> list[str]:
    session_names = glob.glob("sessions/*.session")
    session_names = [
        os.path.splitext(os.path.basename(file))[0] for file in session_names
    ]

    return session_names

def get_proxies() -> list[Proxy]:
    if settings.USE_PROXY_FROM_FILE:
        with open(file="proxies.txt", encoding="utf-8-sig") as file:
            proxies = [Proxy.from_str(proxy=row.strip()).as_url for row in file]
    else:
        proxies = []

    return proxies

async def get_tg_clients() -> list[Client]:
    global tg_clients

    session_names = get_session_names()

    if not session_names:
        raise FileNotFoundError(localization.get_message('launcher', 'no_sessions_found'))

    if not settings.API_ID or not settings.API_HASH:
        raise ValueError(localization.get_message('launcher', 'api_not_set'))

    tg_clients = [
        Client(
            name=session_name,
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
            workdir="sessions/",
        )
        for session_name in session_names
    ]

    return tg_clients