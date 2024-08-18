import asyncio
import argparse
from itertools import cycle
from .config import *
from .utils import *
from bot.utils.telegram_bot import run_bot
from bot.core.tapper import run_tapper


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