import os
import glob
import asyncio
import argparse
from itertools import cycle

from pyrogram import Client
from better_proxy import Proxy

from bot.config.config import settings
from bot.config.config import localization
from bot.utils import logger
from bot.utils.TelegramBot import run_bot
from bot.core.tapper import run_tapper
from bot.core.registrator import register_sessions

global tg_clients

def get_session_names() -> list[str]:
    session_names = glob.glob("sessions/*.session")
    session_names = [
        os.path.splitext(os.path.basename(file))[0] for file in session_names
    ]

    return session_names

def get_proxies() -> list[Proxy]:
    if settings.USE_PROXY_FROM_FILE:
        with open(file="bot/config/proxies.txt", encoding="utf-8-sig") as file:
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

async def process() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--action", type=int, help="Action to perform")
    logger.info(localization.get_message('launcher', 'sessions_proxies_info').format(len(get_session_names()), len(get_proxies())))

    action = parser.parse_args().action

    if not action:
        print(localization.get_message('launcher', 'start_text'))

        while True:
            action = input(localization.get_message('launcher', 'input_prompt'))

            if not action.isdigit():
                logger.warning(localization.get_message('launcher', 'input_not_number'))
            elif action not in ["1", "2"]:
                logger.warning(localization.get_message('launcher', 'invalid_action').format(action))
            else:
                action = int(action)
                break

    if action == 2:
        await register_sessions()
    elif action == 1:
        tg_clients = await get_tg_clients()
        asyncio.create_task(run_bot())
        await run_tasks(tg_clients=tg_clients)

async def run_tasks(tg_clients: list[Client]):
    proxies = get_proxies()
    proxies_cycle = cycle(proxies) if proxies else None
    tasks = [
        asyncio.create_task(
            run_tapper(
                tg_client=tg_client,
                proxy=next(proxies_cycle) if proxies_cycle else None,
            )
        )
        for tg_client in tg_clients
    ]

    await asyncio.gather(*tasks)