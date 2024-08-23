import asyncio
from datetime import datetime
from time import time
from typing import Any, Callable
from urllib.parse import unquote, quote
import functools
from copy import deepcopy
import random

import aiohttp
import json
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw import types
from pyrogram.raw.functions.messages import RequestAppWebView

from bot.core.agents import generate_random_user_agent
from ..config import *
from ..utils import logger
from bot.exceptions import InvalidSession
from .headers import *

tapper_instances = {}
_global_gameState = None

def get_global_gameState():
    global _global_gameState
    return _global_gameState

def set_global_gameState(new_state):
    global _global_gameState
    _global_gameState = new_state

def error_handler(func: Callable):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"{args[0].session_name} | {func.__name__} error: {e}")
            await asyncio.sleep(3)
    return wrapper

def retry_with_backoff(retries=5, backoff_in_seconds=1):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if x == retries:
                        raise
                    sleep = backoff_in_seconds * 2 ** x + random.uniform(0, 1)
                    await asyncio.sleep(sleep)
                    x += 1
        return wrapper
    return decorator

class Tapper:
    def __init__(self, tg_client: Client, proxy: str):
        self.tg_client = tg_client
        self.session_name = tg_client.name
        self.proxy = proxy
        self.tg_web_data = None
        self.tg_web_data_not = None

    async def get_tg_web_data(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            if not self.tg_client.is_connected:
                try:
                    await self.tg_client.connect()

                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)
                
            while True:
                try:
                    peer = await self.tg_client.resolve_peer('lost_dogs_bot')
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f"{self.session_name} | FloodWait {fl}")
                    logger.info(f"{self.session_name} | Sleep {fls}s")
                    await asyncio.sleep(fls + 3)
                    
            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                platform='android',
                app=types.InputBotAppShortName(bot_id=peer, short_name="lodoapp"),
                write_allowed=True,
                start_param=settings.REF_ID
            ))

            auth_url = web_view.url

            tg_web_data = unquote(
                string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
            tg_web_data_parts = tg_web_data.split('&')

            user_data = tg_web_data_parts[0].split('=')[1]
            chat_instance = tg_web_data_parts[1].split('=')[1]
            chat_type = tg_web_data_parts[2].split('=')[1]
            start_param = tg_web_data_parts[3].split('=')[1]
            auth_date = tg_web_data_parts[4].split('=')[1]
            hash_value = tg_web_data_parts[5].split('=')[1]

            user_data_encoded = quote(user_data)

            init_data = (f"user={user_data_encoded}&chat_instance={chat_instance}&chat_type={chat_type}&"
                         f"start_param={start_param}&auth_date={auth_date}&hash={hash_value}")

            me = await self.tg_client.get_me()
            self.tg_client_id = me.id
            
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return init_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(localization.get_message('tapper', 'unknown_error').format(self.session_name, error))
            await asyncio.sleep(delay=3)
    
    
    async def get_tg_web_data_not(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            with_tg = True

            if not self.tg_client.is_connected:
                with_tg = False
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            while True:
                try:
                    peer = await self.tg_client.resolve_peer('notgames_bot')
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f"<light-yellow>{self.session_name}</light-yellow> | FloodWait {fl}")
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Sleep {fls}s")

                    await asyncio.sleep(fls + 3)

            InputBotApp = types.InputBotAppShortName(bot_id=peer, short_name="squads")

            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                app=InputBotApp,
                platform='android',
                write_allowed=True,
            ))

            auth_url = web_view.url
            tg_web_data = unquote(
                string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])

            if with_tg is False:
                await self.tg_client.disconnect()

            return tg_web_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(localization.get_message('tapper', 'unknown_error').format(self.session_name, error))
            await asyncio.sleep(delay=3)
            
    @retry_with_backoff()
    async def make_request(self, http_client, method, endpoint=None, url=None, **kwargs):
        full_url = url or f"https://api.getgems.io/graphql{endpoint or ''}"
        async with http_client.request(method, full_url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()
    
    async def game_urls(self, http_client, type):
        urls = {
            
            'dogsPage': "?operationName=getDogsPage&variables=%7B%22withCommonTasks%22%3Atrue%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%22a23b386ba13302517841d83364cd25ea6fcbf07e1a34a40a5314da8cfd1c6565%22%7D%7D",
            'homePage': "?operationName=getHomePage&variables=%7B%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%226d07a34b66170fe08f878f8d8b000a5611bd7c8cee8729e5dc41ae848fab4352%22%7D%7D",
            'personalTasks': "?operationName=lostDogsWayWoofPersonalTasks&variables=%7B%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%22d94df8d9fce5bfdd4913b6b3b6ab71e2f9d6397e2a17de78872f604b9c53fe79%22%7D%7D"
        }
        return await self.make_request(http_client, 'GET', urls[type])

    
    @error_handler
    @retry_with_backoff()
    async def get_info_data(self, http_client):
        response = await self.game_urls(http_client, "homePage")
        home_page_data = response.get('data', {})
        
        if not home_page_data:
            error = response.get("errors", [{}])[0].get("message")
            if error == "User not found":
                register_response = await self.register_user(http_client=http_client)
                if register_response:
                    logger.success(localization.get_message('tapper', 'user_registered').format(self.session_name, register_response['nickname'], register_response['id']))
                    await asyncio.sleep(delay=random.randint(3, 7))
                    return await self.get_info_data(http_client=http_client)
            else:
                logger.error(localization.get_message('tapper', 'server_error').format(self.session_name, error))
                await asyncio.sleep(delay=random.randint(3, 7))
        
        game_status = home_page_data.get('lostDogsWayGameStatus', None)
        user_info = home_page_data.get('lostDogsWayUserInfo', None)
        
        if game_status and game_status.get('gameState', {}):
            set_global_gameState(game_status['gameState'])
        
        json_data = {
            'launch': True,
            'timeMs': int(time() * 1000)
        }
        await self.save_game_event(http_client=http_client, data=json_data, event_name="Launch")
        
        return game_status, user_info

    @error_handler
    @retry_with_backoff()
    async def register_user(self, http_client):
        json_data = {
            "operationName": "lostDogsWayGenerateWallet",
            "variables": {},
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "d78ea322cda129ec3958fe21013f35ab630830479ea9510549963956127a44dd"
                }
            }
        }
        response = await self.make_request(http_client, 'POST', json=json_data)
        return response['data']['lostDogsWayGenerateWallet']['user']
    
    @error_handler
    @retry_with_backoff()
    async def process_tasks(self, http_client):
        tasks = await self.game_urls(http_client, 'dogsPage')
        personal_tasks = await self.game_urls(http_client, 'personalTasks')
        done_tasks = tasks.get('data',{}).get('lostDogsWayUserCommonTasksDone', {})
        common_tasks = tasks.get('data',{}).get('lostDogsWayCommonTasks', {})
        
        await self.save_game_event(http_client, {"commonPageView": "yourDog", "timeMs": int(time() * 1000)}, "Common Page View")
        
        for task in personal_tasks.get('data', {}).get('lostDogsWayWoofPersonalTasks', {}).get('items'):
            if not task.get('isCompleted') and task.get('id') not in ['connectWallet', 'joinSquad']:
                await asyncio.sleep(random.randint(5, 10))
                logger.info(localization.get_message('tapper', 'processing_tasks').format(self.session_name, task['name']))
                response_data = await self.perform_task(http_client, task['id'])
                if response_data and response_data.get('success', False) is True:
                    reward_amount = int(response_data.get('woofReward', 0)) / 1000000000
                    logger.success(localization.get_message('tapper', 'task_completed').format(self.session_name, response_data['task']['name'], reward_amount))
                else:
                    logger.info(localization.get_message('tapper', 'task_failed').format(self.session_name, task['name']))
                    
        for task in common_tasks.get('items'):
            if task.get('id') not in done_tasks and task.get('customCheckStrategy') is None:
                await asyncio.sleep(random.randint(5, 10))
                logger.info(localization.get_message('tapper', 'processing_tasks').format(self.session_name, task['name']))
                response_data = (await self.perform_common_task(http_client, task['id'])).get('data', {}).get('lostDogsWayCompleteCommonTask', {})
                if response_data and response_data.get('success', False) is True:
                    reward_amount = int(response_data.get('woofReward', 0)) / 1000000000
                    logger.success(localization.get_message('tapper', 'task_completed').format(self.session_name, response_data['task']['name'], reward_amount))
                else:
                    logger.info(localization.get_message('tapper', 'task_failed').format(self.session_name, task['name']))


    @error_handler
    @retry_with_backoff()
    async def perform_task(self, http_client, task_id):
        json_data = {
            "operationName": "lostDogsWayCompleteTask",
            "variables": {"type": task_id},
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "4c8a2a1192a55e9e84502cdd7a507efd5c98d3ebcb147e307dafa3ec40dca60a"
                }
            }
        }
        return await self.make_request(http_client, 'POST', json=json_data)
    
    @error_handler
    @retry_with_backoff()
    async def perform_common_task(self, http_client, task_id):
        json_data = {
            "operationName": "lostDogsWayCompleteCommonTask",
            "variables": {"id": task_id},
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "313971cc7ece72b8e8edce3aa0bc72f6e40ef1c242250804d72b51da20a8626d"
                }
            }
        }
        response = await self.make_request(http_client, 'POST', json=json_data)
        await self.save_game_event(http_client, {'timeMs': int(time() * 1000), 'yourDogGetFreeDogs': True}, "Complete Task")
        return response

    @error_handler
    @retry_with_backoff()
    async def join_squad(self, http_client: aiohttp.ClientSession, card_number: int):
        squad_options = {1: "whogm", 2: "hadgm", 3: "fewgm"}
        squad = squad_options.get(card_number, "whogm")
        local_headers = deepcopy(headers_notcoin)

        response = await http_client.post('https://api.notcoin.tg/auth/login', headers=local_headers,
                                          json={"webAppData": self.tg_web_data_not})
        accessToken = json.loads(await response.text()).get("data", {}).get("accessToken")

        if not accessToken:
            logger.error(localization.get_message('tapper', 'x_auth_token_not_found').format(self.session_name))
            return

        local_headers['X-Auth-Token'] = f'Bearer {accessToken}'
        info_response = await http_client.get(url=f'https://api.notcoin.tg/squads/by/slug/{squad}',
                                              headers=local_headers)
        info_json = await info_response.json()
        chat_id = info_json['data']['squad']['chatId']

        join_response = await http_client.post(f'https://api.notcoin.tg/squads/{squad}/join', headers=local_headers,
                                               json={'chatId': chat_id})

        if join_response.status in [200, 201]:
            logger.success(localization.get_message('tapper', 'squad_join_success').format(self.session_name, squad))
        else:
            logger.warning(localization.get_message('tapper', 'squad_join_fail').format(self.session_name, squad, join_response.status))


    @error_handler
    @retry_with_backoff()
    async def way_vote(self, http_client, card_number):
        await self.join_squad(http_client=http_client, card_number=card_number) # Вступаем в сквад
        await asyncio.sleep(delay=3)
        await self.save_game_event(http_client, {"mainScreenVote": True, "timeMs": int(time() * 1000)}, "MainScreen Vote")
        await asyncio.sleep(random.randint(1, 3))
        
        json_data = {
            "operationName": "lostDogsWayVote",
            "variables": {"value": str(card_number)},
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "6fc1d24c3d91a69ebf7467ebbed43c8837f3d0057a624cdb371786477c12dc2f"
                }
            }
        }
        return await self.make_request(http_client, 'POST', json=json_data)
    
    
    @error_handler
    @retry_with_backoff()
    async def view_prev_round(self, http_client: aiohttp.ClientSession):
        json_data = {
            "operationName": "lostDogsWayViewPrevRound",
            "variables": {},
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "9d71c4ff04d1f8ec24f23decd0506e7b1b8a0c70ea6bb4c98fcaf6904eb96c35"
                }
            }
        }
        return await self.make_request(http_client, 'POST', json=json_data)
    
    @error_handler
    @retry_with_backoff()
    async def save_game_event(self, http_client: aiohttp.ClientSession, data: Any, event_name: str):
        json_data = {
            "operationName": "lostDogsWaySaveEvent",
            "variables": {
                "data": {
                    "events": [data],
                    "utm": {
                        "campaign": None,
                        "content": None,
                        "medium": None,
                        "source": None,
                        "term": None
                    }
                }
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "0b910804d22c9d614a092060c4f1809ee6e1fc0625ddb30ca08ac02bac32936a"
                }
            }
        }
        response = await self.make_request(http_client, 'POST', json=json_data)
        if not response['data']['lostDogsWaySaveEvent']:
            logger.warning(localization.get_message('tapper', 'save_event_failed').format(self.session_name, event_name))
    
    
    @error_handler
    @retry_with_backoff()
    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        response = await self.make_request(http_client, 'GET', url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
        ip = response.get('origin')
        logger.info(localization.get_message('tapper', 'proxy_check').format(self.session_name, ip))

    @error_handler
    async def run_bot_cycle(self, http_client, card_number: int = None):
        if settings.USE_RANDOM_DELAY_IN_RUN:
            random_delay = random.randint(settings.RANDOM_DELAY_IN_RUN[0], settings.RANDOM_DELAY_IN_RUN[1])
            logger.info(localization.get_message('tapper', 'random_delay').format(self.session_name, random_delay))
            await asyncio.sleep(random_delay)
        
        self.tg_web_data = await self.get_tg_web_data(proxy=self.proxy)
        self.tg_web_data_not = await self.get_tg_web_data_not(proxy=self.proxy)
        http_client.headers["X-Auth-Token"] = self.tg_web_data
        
        game_status, user_info = await self.get_info_data(http_client)
        if game_status is None or user_info is None:
            sleep_time = random.randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])
            logger.error(localization.get_message('tapper', 'info_data_none'))
            logger.info(localization.get_message('tapper', 'sleep_info').format(self.session_name, sleep_time))
            await asyncio.sleep(delay=sleep_time)
            return
        
        
        bones_balance = user_info['gameDogsBalance']
        woof_balance = int(user_info['woofBalance']) / 1000000000
        logger.info(localization.get_message('tapper', 'balance_info').format(self.session_name, bones_balance, woof_balance))
        
        prev_round_data = user_info['prevRoundVote']
        if isinstance(user_info.get('squad'), dict):
            squad_name = user_info.get('squad', {}).get("name", localization.get_message('tapper', 'unknown_clan'))
            logger.info(localization.get_message('tapper', 'squad_info_member').format(self.session_name, squad_name))
        else:
            logger.info(localization.get_message('tapper', 'squad_info_no_member').format(self.session_name))
            
        if prev_round_data:
            logger.info(localization.get_message('tapper', 'previous_round_completed').format(self.session_name))
            prize = round(int(prev_round_data['woofPrize']) / 1000000000, 2)
            if prev_round_data['userStatus'] == 'winner':
                not_prize = round(int(prev_round_data['notPrize']) / 1000000000, 2)
                logger.success(localization.get_message('tapper', 'successful_prediction').format(self.session_name, prize, not_prize))
            elif prev_round_data['userStatus'] == 'loser':
                logger.info(localization.get_message('tapper', 'incorrect_prediction').format(self.session_name, prize))

            await self.view_prev_round(http_client=http_client)
            await asyncio.sleep(delay=2)

        await self.process_tasks(http_client=http_client)
        await asyncio.sleep(delay=random.randint(5, 10))               
        
        current_round = user_info.get('currentRoundVote', None)
        if current_round is None:
            if card_number is not None:
                await self.way_vote(http_client=http_client, card_number=card_number)
                logger.info(localization.get_message('tapper', 'vote_card').format(self.session_name, card_number))
        else:
            if isinstance(current_round, dict) and 'selectedRoundCardValue' in current_round and 'spentGameDogsCount' in current_round:
                card = current_round['selectedRoundCardValue']
                spend_bones = current_round['spentGameDogsCount']
                logger.info(localization.get_message('tapper', 'vote_success').format(self.session_name, card, spend_bones))
            else:
                logger.warning(localization.get_message('tapper', 'invalid_round_data').format(self.session_name, current_round))

        if game_status and 'gameState' in game_status:
            game_end_at = datetime.fromtimestamp(int(game_status['gameState'].get('gameEndsAt', 0)))
            round_end_at = max(game_status['gameState'].get('roundEndsAt', 0) - time(), 0)
            logger.info(localization.get_message('tapper', 'game_status').format(self.session_name, int(round_end_at / 60), game_end_at))
            
        sleep_time = random.randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])
        logger.info(localization.get_message('tapper', 'sleep_info').format(self.session_name, sleep_time))
        await asyncio.sleep(delay=sleep_time)

    async def run(self) -> None:
        proxy_conn = ProxyConnector().from_url(self.proxy) if self.proxy else None

        async with CloudflareScraper(headers=headers, connector=proxy_conn) as http_client:
            if settings.FAKE_USERAGENT:
                http_client.headers["User-Agent"] = generate_random_user_agent(device_type='android', browser_type='chrome')
            
            if self.proxy:
                await self.check_proxy(http_client=http_client, proxy=self.proxy)
                
            while True:
                await self.run_bot_cycle(http_client, random.randint(1, 3) if settings.RANDOM_CARD else None)

    async def handle_telegram_command(self, card_number):
        proxy_conn = ProxyConnector().from_url(self.proxy) if self.proxy else None
        
        async with CloudflareScraper(headers=headers, connector=proxy_conn) as http_client:
            if settings.FAKE_USERAGENT:
                http_client.headers["User-Agent"] = generate_random_user_agent(device_type='android', browser_type='chrome')
            
            if self.proxy:
                await self.check_proxy(http_client=http_client, proxy=self.proxy)
            
            await self.run_bot_cycle(http_client, card_number)
        
async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        tapper = Tapper(tg_client=tg_client, proxy=proxy)
        tapper_instances[tg_client.name] = tapper
        await tapper.run()
    except InvalidSession:
        logger.error(localization.get_message('tapper', 'invalid_session').format(tg_client.name))
        if tg_client.name in tapper_instances:
            del tapper_instances[tg_client.name]

async def vote_card_for_all_tappers(card_input: str):
    tasks = []
    for tapper in tapper_instances.values():
        task = asyncio.create_task(tapper.handle_telegram_command(choose_card(card_input)))
        tasks.append(task)
    
    await asyncio.gather(*tasks)

async def vote_card_for_tapper_by_name(session_name: str, card_input: str):
    tapper = tapper_instances.get(session_name)
    if tapper:
        await tapper.handle_telegram_command(choose_card(card_input))
    else:
        logger.error(localization.get_message('tapper', 'session_not_found').format(session_name))

def choose_card(card_input: str) -> int:
    if ',' in card_input:
        options = [int(card.strip()) for card in card_input.split(',')]
        return random.choice(options)
    elif card_input == '0':
        return random.randint(1, 3)
    else:
        return int(card_input)