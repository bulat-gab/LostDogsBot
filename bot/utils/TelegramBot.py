from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
from time import time
from bot.core.tapper import vote_card_for_all_tappers, vote_card_for_tapper_by_name, tapper_instances
from bot.config.config import settings, localization
from bot.utils import logger

class TelegramBot:
    def __init__(self, token: str):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()

    async def start(self):
        self.dp.message.register(self.start_handler, CommandStart())
        self.dp.callback_query.register(self.process_callback)
        
        await self.dp.start_polling(self.bot)

    def get_main_keyboard(self):
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text=localization.get_button_text('vote'), callback_data="vote"))
        keyboard.row(InlineKeyboardButton(text=localization.get_button_text('current_round'), callback_data="current_round"))
        keyboard.row(InlineKeyboardButton(text=localization.get_button_text('list_tappers'), callback_data="list_tappers"))
        keyboard.row(InlineKeyboardButton(text=localization.get_button_text('vote_tapper'), callback_data="vote_tapper"))
        return keyboard.as_markup()

    async def start_handler(self, message: types.Message):
        if message.from_user.id == settings.ADMIN_UID:
            await message.answer(localization.get_message('telegram_bot', 'greeting_admin'), reply_markup=self.get_main_keyboard())
        else:
            await message.answer(localization.get_message('telegram_bot', 'no_access'))

    async def process_callback(self, callback_query: types.CallbackQuery):
        if str(callback_query.from_user.id) not in str(settings.ADMIN_UID):
            await callback_query.answer(localization.get_message('telegram_bot', 'no_access_command'))
            return

        action = callback_query.data.split(':')[0]

        if action == "back_to_main":
            await callback_query.message.edit_text(localization.get_message('telegram_bot', 'select_action'), reply_markup=self.get_main_keyboard())
        elif action == "vote":
            await self.vote_handler(callback_query)
        elif action == "current_round":
            await self.current_round(callback_query)
        elif action == "list_tappers":
            await self.list_tappers_handler(callback_query)
        elif action == "vote_tapper":
            await self.vote_tapper_handler(callback_query)
        elif action.startswith("select_tapper"):
            tapper_name = callback_query.data.split(':')[1]
            await self.select_card_for_tapper(callback_query, tapper_name)
        elif action.startswith("vote_card"):
            card_number = callback_query.data.split(':')[1]
            tapper_name = callback_query.data.split(':')[2] if len(callback_query.data.split(':')) > 2 else None
            await self.process_card_vote(callback_query, card_number, tapper_name)

    async def vote_handler(self, callback_query: types.CallbackQuery):
        gameState = await getGameState()
        if gameState is None:
            keyboard = InlineKeyboardBuilder()
            keyboard.row(InlineKeyboardButton(text=localization.get_button_text('back'), callback_data="back_to_main"))
            await callback_query.message.edit_text(localization.get_message('telegram_bot', 'game_state_null'), reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)
            return

        keyboard = InlineKeyboardBuilder()
        card_info = localization.get_message('telegram_bot', 'vote_info').format(gameState['description'], localization.get_task_type(gameState['taskType']))
        for card in gameState['roundCards']:
            card_info += f"{card['number']}. {card['name']}\n"
            keyboard.row(InlineKeyboardButton(text=f"{card['number']}. {card['name']}", callback_data=f"vote_card:{card['number']}"))
        
        keyboard.row(InlineKeyboardButton(text=localization.get_button_text('random_card'), callback_data="vote_card:0"))
        keyboard.row(InlineKeyboardButton(text=f"{gameState['roundCards'][0]['name']} или {gameState['roundCards'][1]['name']}", callback_data="vote_card:1,2"))
        keyboard.row(InlineKeyboardButton(text=f"{gameState['roundCards'][0]['name']} или {gameState['roundCards'][2]['name']}", callback_data="vote_card:1,3"))
        keyboard.row(InlineKeyboardButton(text=f"{gameState['roundCards'][1]['name']} или {gameState['roundCards'][2]['name']}", callback_data="vote_card:2,3"))
        keyboard.row(InlineKeyboardButton(text=localization.get_button_text('back'), callback_data="back_to_main"))
        
        await callback_query.message.edit_text(f"{card_info}\n{localization.get_message('telegram_bot', 'select_card')}", reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)

    async def vote_tapper_handler(self, callback_query: types.CallbackQuery):
        keyboard = InlineKeyboardBuilder()
        for tapper_name in tapper_instances.keys():
            keyboard.row(InlineKeyboardButton(text=tapper_name, callback_data=f"select_tapper:{tapper_name}"))
        keyboard.row(InlineKeyboardButton(text=localization.get_button_text('back'), callback_data="back_to_main"))
        await callback_query.message.edit_text(localization.get_message('telegram_bot', 'select_tapper'), reply_markup=keyboard.as_markup())

    async def select_card_for_tapper(self, callback_query: types.CallbackQuery, tapper_name: str):
        gameState = await getGameState()
        if gameState is None:
            keyboard = InlineKeyboardBuilder()
            keyboard.row(InlineKeyboardButton(text=localization.get_button_text('back'), callback_data="back_to_main"))
            await callback_query.message.edit_text(localization.get_message('telegram_bot', 'game_state_null'), reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)
            return

        keyboard = InlineKeyboardBuilder()
        card_info = localization.get_message('telegram_bot', 'vote_info').format(gameState['description'], localization.get_task_type(gameState['taskType']))
        card_info += localization.get_message('telegram_bot', 'vote_for_tapper').format(tapper_name)
        for card in gameState['roundCards']:
            card_info += f"{card['number']}. {card['name']}\n"
            keyboard.row(InlineKeyboardButton(text=f"{card['number']}. {card['name']}", callback_data=f"vote_card:{card['number']}:{tapper_name}"))
        
        keyboard.row(InlineKeyboardButton(text=localization.get_button_text('back'), callback_data="vote_tapper"))
        
        await callback_query.message.edit_text(f"{card_info}\n{localization.get_message('telegram_bot', 'select_card_for_tapper').format(tapper_name)}", reply_markup=keyboard.as_markup())

    async def process_card_vote(self, callback_query: types.CallbackQuery, card_number: str, tapper_name: str = None):
        gameState = await getGameState()
        if gameState is None:
            keyboard = InlineKeyboardBuilder()
            keyboard.row(InlineKeyboardButton(text=localization.get_button_text('back'), callback_data="back_to_main"))
            await callback_query.message.edit_text(localization.get_message('telegram_bot', 'game_state_null'), reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)
            return

        card_name = localization.get_button_text('random_card') if card_number == "0" else next((card['name'] for card in gameState['roundCards'] if str(card['number']) == card_number), "Неизвестная карта")

        if tapper_name:
            message = localization.get_message('telegram_bot', 'vote_success_tapper').format( card_number, card_name, tapper_name)
            asyncio.create_task(vote_card_for_tapper_by_name(tapper_name, card_number))
        else:
            message = localization.get_message('telegram_bot', 'vote_success_all').format( card_number, card_name)
            asyncio.create_task(vote_card_for_all_tappers(card_number))
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text=localization.get_button_text('back'), callback_data="back_to_main"))
        await callback_query.message.edit_text(message, reply_markup=keyboard.as_markup())

    async def current_round(self, callback_query: types.CallbackQuery):
        gameState = await getGameState()
        if gameState is None:
            keyboard = InlineKeyboardBuilder()
            keyboard.row(InlineKeyboardButton(text=localization.get_button_text('back'), callback_data="back_to_main"))
            await callback_query.message.edit_text(localization.get_message('telegram_bot', 'game_state_null'), reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)
            return
        
        round_end_at = max(gameState.get('roundEndsAt', 0) - time(), 0)
        
        info = localization.get_message('telegram_bot', 'current_round_info').format(
                                        int(round_end_at / 60), 
                                        gameState['description'], 
                                        localization.get_task_type(gameState['taskType']))
        
        for card in gameState['roundCards']:
            info += f"\n{card['number']}. {card['name']}"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text=localization.get_button_text('back'), callback_data="back_to_main"))
        await callback_query.message.edit_text(info, reply_markup=keyboard.as_markup())

    async def list_tappers_handler(self, callback_query: types.CallbackQuery):
        tapper_list = "\n".join(tapper_instances.keys())
        cleaned_list = tapper_list.encode('utf-8', errors='ignore').decode('utf-8')
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text=localization.get_button_text('back'), callback_data="back_to_main"))
        await callback_query.message.edit_text(localization.get_message('telegram_bot', 'tapper_list').format(cleaned_list), reply_markup=keyboard.as_markup())

async def getGameState():
    tapper = list(tapper_instances.values())[-1]
    gameState = await tapper.get_gameState()
    if gameState is None:
        return None
    return gameState

async def run_bot():
    if settings.BOT_TOKEN == "" or settings.ADMIN_UID == 0:
        logger.error(localization.get_message('telegram_bot', 'bot_not_started'))
        return
    
    bot = TelegramBot(settings.BOT_TOKEN)
    logger.success(localization.get_message('telegram_bot', 'bot_started_successfully'))
    await bot.start()