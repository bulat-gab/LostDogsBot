import asyncio
from datetime import datetime
from time import time
from typing import Any
from urllib.parse import unquote, quote

import aiohttp
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from random import choice
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered
from pyrogram.raw import types
from pyrogram.raw.functions.messages import RequestAppWebView
from bot.core.agents import generate_random_user_agent
from bot.config import settings

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers

from random import randint

tapper_instances = {}

class Tapper:
    def __init__(self, tg_client: Client, proxy: str):
        self.tg_client = tg_client
        self.tg_client_id = 0
        self.session_name = tg_client.name
        self.proxy = proxy
        self._gameState = None

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
                
            peer = await self.tg_client.resolve_peer('lost_dogs_bot')
            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                platform='android',
                app=types.InputBotAppShortName(bot_id=peer, short_name="lodoapp"),
                write_allowed=True,
                start_param="ref-u_339631649__s_650113"
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
            logger.error(f"{self.session_name} | Неизвестная ошибка при авторизации: {error}")
            await asyncio.sleep(delay=3)

    async def get_info_data(self, http_client: aiohttp.ClientSession):
        try:
            url = ('https://api.getgems.io/graphql?operationName=lostDogsWayUserInfo&variables=%7B%7D&extensions='
                   '%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash'
                   '%22%3A%22a17a9e148547c1c0ab250cca329a3ca237d46b615365dbd217e32aa7c068d10f%22%7D%7D')
            await http_client.options(url=url)

            response = await http_client.get(url=url)
            response.raise_for_status()

            response_json = await response.json()

            if not response_json["data"]:
                error = response_json["errors"][0]["message"]
                if error == "User not found":
                    register_response = await self.register_user(http_client=http_client)
                    if register_response:
                        logger.success(f"{self.session_name} | Пользователь <m>{register_response['nickname']}</m> "
                                       f"успешно зарегистрирован! | ID пользователя: <m>{register_response['id']}</m> ")
                        return await self.get_info_data(http_client=http_client)

                else:
                    logger.error(f"{self.session_name} | Ошибка в ответе от сервера: {error}")
                    await asyncio.sleep(delay=randint(3, 7))

            json_data = {
                'launch': True,
                'timeMs': int(time() * 1000)
            }
            await self.save_game_event(http_client=http_client, data=json_data, event_name="Launch")

            return response_json

        except Exception as error:
            logger.error(f"{self.session_name} | Неизвестная ошибка при получении информации о пользователе: {error}")
            await asyncio.sleep(delay=randint(3, 7))

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"{self.session_name} | IP прокси: {ip}")
        except Exception as error:
            logger.error(f"{self.session_name} | Прокси: {proxy} | Ошибка: {error}")

    async def register_user(self, http_client: aiohttp.ClientSession):
        try:
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

            response = await http_client.post(url='https://api.getgems.io/graphql', json=json_data)
            response.raise_for_status()
            response_json = await response.json()
            return response_json['data']['lostDogsWayGenerateWallet']['user']
        except Exception as error:
            logger.error(f"{self.session_name} | Неизвестная ошибка при регистрации пользователя: {error}")
            await asyncio.sleep(delay=3)

    async def get_personal_tasks(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get(url=f'https://api.getgems.io/graphql?operationName=lostDogsWayWoofPersonalTasks&variables='
                                                 f'%7B%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22'
                                                 f'sha256Hash%22%3A%22d94df8d9fce5bfdd4913b6b3b6ab71e2f9d6397e2a17de78872f604b9c53fe79%22%7D%7D')
            response.raise_for_status()
            response_json = await response.json()
            return response_json['data']['lostDogsWayWoofPersonalTasks']['items']
        except Exception as error:
            logger.error(f"{self.session_name} | Неизвестная ошибка при получении персональных заданий: {error}")
            await asyncio.sleep(delay=3)

    async def get_common_tasks(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get(url=f'https://api.getgems.io/graphql?operationName=lostDogsWayCommonTasks&variables='
                                                 f'%7B%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash'
                                                 f'%22%3A%227c4ca1286c2720dda55661e40d6cb18a8f813bed50c2cf6158d709a116e1bdc1%22%7D%7D')
            response.raise_for_status()
            response_json = await response.json()
            return response_json['data']['lostDogsWayCommonTasks']['items']
        except Exception as error:
            logger.error(f"{self.session_name} | Неизвестная ошибка при получении общих заданий: {error}")
            await asyncio.sleep(delay=3)

    async def processing_tasks(self, http_client: aiohttp.ClientSession):
        try:
            personal_tasks = await self.get_personal_tasks(http_client=http_client)
            await asyncio.sleep(delay=2)
            event_data = {
                "commonPageView": "yourDog",
                "timeMs": int(time() * 1000)
            }
            await self.save_game_event(http_client=http_client, data=event_data, event_name="Common Page View")
            for task in personal_tasks:
                if not task['isCompleted'] and task['id'] != 'connectWallet' and task['id'] != 'joinSquad':
                    await asyncio.sleep(delay=randint(5, 10))
                    logger.info(f"{self.session_name} | Выполнение персонального задания <m>{task['name']}</m>...")
                    response_data = await self.perform_task(http_client=http_client, task_id=task['id'])
                    if response_data and response_data['success']:
                        logger.success(f"{self.session_name} | Задание <m>{response_data['task']['name']}</m> выполнено! | "
                                       f"Награда: <m>+{int(response_data['woofReward']) / 1000000000}</m> $WOOF")
                    else:
                        logger.info(f"{self.session_name} | Не удалось выполнить задание <m>{task['context']['name']}</m>")

            await asyncio.sleep(delay=2)
            common_tasks = await self.get_common_tasks(http_client=http_client)
            done_tasks = await self.get_done_common_tasks(http_client=http_client)
            for task in common_tasks:
                if task['id'] not in done_tasks and task.get('customCheckStrategy') is None:
                    await asyncio.sleep(delay=randint(5, 10))
                    logger.info(f"{self.session_name} | Выполнение общего задания <m>{task['name']}</m>...")
                    response_data = await self.perform_common_task(http_client=http_client, task_id=task['id'])
                    if response_data and response_data['success']:
                        logger.success(f"{self.session_name} | Задание <m>{response_data['task']['name']}</m> выполнено! | "
                                       f"Награда: <m>+{int(response_data['task']['woofReward']) / 1000000000}</m> $WOOF")
                    else:
                        logger.info(f"{self.session_name} | Не удалось выполнить задание <m>{task['context']['name']}</m>")

        except Exception as error:
            logger.error(f"{self.session_name} | Неизвестная ошибка при выполнении заданий: {error}")
            await asyncio.sleep(delay=3)

    async def perform_task(self, http_client: aiohttp.ClientSession, task_id: str):
        try:
            json_data = {
                "operationName": "lostDogsWayCompleteTask",
                "variables": {
                    "type": task_id
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "4c8a2a1192a55e9e84502cdd7a507efd5c98d3ebcb147e307dafa3ec40dca60a"
                    }
                }
            }

            response = await http_client.post(url=f'https://api.getgems.io/graphql', json=json_data)
            response.raise_for_status()
            response_json = await response.json()
            return response_json['data']['lostDogsWayCompleteTask']

        except Exception as e:
            logger.error(f"{self.session_name} | Неизвестная ошибка при проверке персонального задания {task_id} | Ошибка: {e}")

    async def perform_common_task(self, http_client: aiohttp.ClientSession, task_id: str):
        try:
            json_data = {
                "operationName": "lostDogsWayCompleteCommonTask",
                "variables": {
                    "id": task_id
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "313971cc7ece72b8e8edce3aa0bc72f6e40ef1c242250804d72b51da20a8626d"
                    }
                }
            }

            response = await http_client.post(url=f'https://api.getgems.io/graphql', json=json_data)
            response.raise_for_status()
            response_json = await response.json()

            event_data = {
                'timeMs': int(time() * 1000),
                'yourDogGetFreeDogs': True
            }
            await self.save_game_event(http_client, data=event_data, event_name="Complete Task")
            if response_json['data'] is None and response_json['errors']:
                error = response_json['errors'][0]['message']
                if error == "Task cannot be checked":
                    logger.info(f"{self.session_name} | Задание <m>{task_id}</m> без награды")
                    return None

            return response_json['data']['lostDogsWayCompleteCommonTask']

        except Exception as e:
            logger.error(f"{self.session_name} | Неизвестная ошибка при проверке общего задания {task_id} | Ошибка: {e}")

    async def get_done_common_tasks(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get(url=f'https://api.getgems.io/graphql?operationName=lostDogsWayUserCommonTasksDone&variables='
                                                 f'%7B%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22'
                                                 f'sha256Hash%22%3A%2299a387150779864b6b625e336bfd28bbc8064b66f9a1b6a55ee96b8777678239%22%7D%7D')
            response.raise_for_status()
            response_json = await response.json()
            return response_json['data']['lostDogsWayUserCommonTasksDone']
        except Exception as error:
            logger.error(f"{self.session_name} | Неизвестная ошибка при получении выполненных заданий: {error}")
            await asyncio.sleep(delay=3)

    async def get_game_status(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get(f'https://api.getgems.io/graphql?operationName=lostDogsWayGameStatus&variables='
                                             f'%7B%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash'
                                             f'%22%3A%22f706c4cd57a87632bd4360b5458e65f854b07e690cf7f8b9f96567fe072148c1%22%7D%7D')
            response_json = await response.json()
            return response_json['data']['lostDogsWayGameStatus']
        except Exception as error:
            logger.error(f"{self.session_name} | Неизвестная ошибка при получении статуса игры: {error}")
            await asyncio.sleep(delay=3)

    async def view_prev_round(self, http_client: aiohttp.ClientSession):
        try:
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
            response = await http_client.post(f'https://api.getgems.io/graphql', json=json_data)
            response_json = await response.json()
            return response_json['data']['lostDogsWayViewPrevRound']
        except Exception as error:
            logger.error(f"{self.session_name} | Неизвестная ошибка при получении статуса игры: {error}")
            await asyncio.sleep(delay=3)

    async def save_game_event(self, http_client: aiohttp.ClientSession, data: Any, event_name: str):
        try:
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
            response = await http_client.post(f'https://api.getgems.io/graphql', json=json_data)
            response_json = await response.json()
            if not response_json['data']['lostDogsWaySaveEvent']:
                logger.warning(f"{self.session_name} | Не удалось сохранить игровое событие: <m>{event_name}</m>")
        except Exception as error:
            logger.error(f"{self.session_name} | Неизвестная ошибка при сохранении игрового события: {error}")
            await asyncio.sleep(delay=3)
            
    async def join_squad(self, http_client: aiohttp.ClientSession, card_number: int):
        squad_options = {
            1: "whogm",
            2: "hadgm",
            3: "fewgm"
        }
        try:
            response = await http_client.get(f'https://api.notcoin.tg/profiles/by/telegram_id/{self.tg_client_id}')
            response.raise_for_status()
            x_auth_token = response.headers.get('X-Auth-Token')

            if not x_auth_token:
                logger.error(f"{self.session_name} | Не удалось получить X-Auth-Token")
                return

            squad = squad_options.get(card_number, "whogm")
            headers = {'X-Auth-Token': x_auth_token}
            join_response = await http_client.get(f'https://api.notcoin.tg/squads/{squad}/join', headers=headers)
            join_response.raise_for_status()

            if join_response.status == 200:
                logger.success(f"{self.session_name} | Успешно присоединились к отряду {squad}")
            else:
                logger.warning(f"{self.session_name} | Не удалось присоединиться к отряду {squad}. Статус: {join_response.status}")

        except Exception as error:
            logger.error(f"{self.session_name} | Ошибка при присоединении к отряду: {error}")

    async def way_vote(self, http_client: aiohttp.ClientSession, card_number: int = None):
        try:
            event_data = {
                    "mainScreenVote": True,
                    "timeMs": int(time() * 1000)
                }
            #await self.join_squad(http_client=http_client, card_number=card_number) # Вступаем в сквад
            await self.save_game_event(http_client, event_data, event_name="MainScreen Vote")
            await asyncio.sleep(delay=randint(1, 3))
            
            json_data = {
                "operationName": "lostDogsWayVote",
                "variables": {
                    "value": str(card_number)
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "6fc1d24c3d91a69ebf7467ebbed43c8837f3d0057a624cdb371786477c12dc2f"
                    }
                }
            }

            response = await http_client.post(f'https://api.getgems.io/graphql', json=json_data)
            response_json = await response.json()
            response.raise_for_status()

            response_data = response_json['data']['lostDogsWayVote']
            card = response_data['selectedRoundCardValue']
            spend_bones = response_data['spentGameDogsCount']

            logger.success(f"{self.session_name} | Успешное голосование! | Выбранная карта: <m>{card}</m> | "
                               f"Потрачено костей: <m>{spend_bones}</m> ")

            return response_data

        except Exception as error:
            logger.error(f"{self.session_name} | Неизвестная ошибка при голосовании: {error}")
            await asyncio.sleep(delay=3)
            
    async def safe_gameState(self, gameState):
        self._gameState = gameState
        
        
    async def get_gameState(self):
        return self._gameState
    
    
    async def run_bot_cycle(self, http_client, card_number: int = None):
        try:
            if settings.USE_RANDOM_DELAY_IN_RUN:
                random_delay = randint(settings.RANDOM_DELAY_IN_RUN[0], settings.RANDOM_DELAY_IN_RUN[1])
                logger.info(f"{self.session_name} |  Бот запустится через <lw>{random_delay}s</lw>")
                await asyncio.sleep(delay=random_delay)
            tg_web_data = await self.get_tg_web_data(proxy=self.proxy)
            http_client.headers["X-Auth-Token"] = tg_web_data
            user_info = await self.get_info_data(http_client=http_client)
            
            bones_balance = user_info['data']['lostDogsWayUserInfo']['gameDogsBalance']
            woof_balance = int(user_info['data']['lostDogsWayUserInfo']['woofBalance']) / 1000000000
            logger.info(
                f"{self.session_name} | Баланс: Кости = <m>{bones_balance}</m>; $WOOF = <m>{woof_balance}</m>")
            prev_round_data = user_info['data']['lostDogsWayUserInfo']['prevRoundVote']
            if prev_round_data:
                
                logger.info(f"{self.session_name} | Предыдущий раунд завершен | Получение наград за прогноз...")
                # squad = user_info['data']['lostDogsWayUserInfo']['squad']
                # squad_name = squad.get("name", 'Неизвестный клан')
                # logger.info(f"{self.session_name} | Вы были в клане <m>{squad_name}</m>") 
                prize = round(int(prev_round_data['woofPrize']) / 1000000000, 2)
                if prev_round_data['userStatus'] == 'winner':
                    not_prize = round(int(prev_round_data['notPrize']) / 1000000000, 2)
                    
                    logger.success(f"{self.session_name} | Успешное предсказание карты! | "
                                    f"Вы получили <m>{prize}</m> $WOOF и <m>{not_prize}</m> $NOT")
                elif prev_round_data['userStatus'] == 'loser':
                    logger.info(f"{self.session_name} | Неверное предсказание карты | Вы получили <m>{prize}</m> $WOOF")

                await self.view_prev_round(http_client=http_client)
                await asyncio.sleep(delay=2)

            await self.processing_tasks(http_client=http_client)
            await asyncio.sleep(delay=randint(5, 10))               
            
            current_round = user_info['data']['lostDogsWayUserInfo'].get('currentRoundVote')
            if current_round is None:
                if card_number is not None:
                    await self.way_vote(http_client=http_client, card_number=card_number)
                    logger.info(f"{self.session_name} | Проголосовали за карту: <m>{card_number}</m>")
            else:
                if isinstance(current_round, dict) and 'selectedRoundCardValue' in current_round and 'spentGameDogsCount' in current_round:
                    card = current_round['selectedRoundCardValue']
                    spend_bones = current_round['spentGameDogsCount']
                    logger.info(
                        f"{self.session_name} | Проголосовали за карту: <m>{card}</m> | Потрачено костей: <m>{spend_bones}</m>"
                    )
                else:
                    logger.warning(f"{self.session_name} | Некорректные данные текущего раунда: {current_round}")

            game_status = await self.get_game_status(http_client=http_client)
            if game_status and 'gameState' in game_status:
                await self.safe_gameState(game_status['gameState'])
                game_end_at = datetime.fromtimestamp(int(game_status['gameState'].get('gameEndsAt', 0)))
                round_end_at = max(game_status['gameState'].get('roundEndsAt', 0) - time(), 0)
                logger.info(
                    f"{self.session_name} | Текущий раунд заканчивается через: <m>{int(round_end_at / 60)}</m> мин | "
                    f"Игра заканчивается: <m>{game_end_at}</m>")
            else:
                logger.warning(f"{self.session_name} | Не удалось получить статус игры")
                
            sleep_time = randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])
            logger.info(f"{self.session_name} | Сон <m>{sleep_time}</m> секунд")
            await asyncio.sleep(delay=sleep_time)

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | Неизвестная ошибка: {error}")
            await asyncio.sleep(delay=randint(60, 120))
    
    async def run(self) -> None:
        proxy_conn = ProxyConnector().from_url(self.proxy) if self.proxy else None

        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)
        
        if settings.FAKE_USERAGENT:
            http_client.headers["User-Agent"] = generate_random_user_agent(device_type='android', browser_type='chrome')
        
        if self.proxy:
            await self.check_proxy(http_client=http_client, proxy=self.proxy)
            
        while True:
            await self.run_bot_cycle(http_client, randint(1, 3) if settings.RANDOM_CARD else None)
    
    async def handle_telegram_command(self, card_number):
        proxy_conn = ProxyConnector().from_url(self.proxy) if self.proxy else None
        
        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)
        
        if settings.FAKE_USERAGENT:
            http_client.headers["User-Agent"] = generate_random_user_agent(device_type='android', browser_type='chrome')
        
        if self.proxy:
            await self.check_proxy(http_client=http_client, proxy=self.proxy)
        
        await self.run_bot_cycle(http_client, card_number)

tapper_instances = {}

async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        tapper = Tapper(tg_client=tg_client, proxy=proxy)
        tapper_instances[tg_client.name] = tapper
        await tapper.run()
    except InvalidSession:
        logger.error(f"{tg_client.name} | Недействительная сессия")
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
        logger.error(f"Сессия {session_name} не найдена")

def choose_card(card_input: str) -> int:
    if ',' in card_input:
        options = [int(card.strip()) for card in card_input.split(',')]
        return choice(options)
    elif card_input == '0':
        return randint(1, 3)
    else:
        return int(card_input)