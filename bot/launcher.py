import asyncio
import argparse

from bot.utils.proxy_utils_v1 import create_tg_client_proxy_pairs
from .config import *
from .utils import *
from bot.utils.telegram_bot import run_bot
from bot.core.tapper import run_tapper


async def process() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--action", type=int, help="Action to perform")

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
    client_proxy_list = create_tg_client_proxy_pairs(tg_clients)

    tasks = [
        asyncio.create_task(
            run_tapper(
                tg_client=pair[0],
                proxy=pair[1].as_url,
            )
        )
        for pair in client_proxy_list
    ]

    await asyncio.gather(*tasks)