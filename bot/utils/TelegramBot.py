from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from bot.core.tapper import vote_card_for_all_tappers, vote_card_for_tapper_by_name, tapper_instances
from bot.config import settings

class TelegramBot:
    def __init__(self, token: str):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()

    async def start(self):
        self.dp.message(Command("start"))(self.start_handler)
        self.dp.message(Command("vote"))(self.vote_handler)
        self.dp.message(Command("list_tappers"))(self.list_tappers_handler)
        self.dp.message(Command("vote_tapper"))(self.vote_tapper_handler)
        await self.bot.set_my_commands([
            types.BotCommand(command="vote", description="Проголосовать всем сессиям"),
            types.BotCommand(command="list_tappers", description="Вывести список активных сессий"),
            types.BotCommand(command="vote_tapper", description="Проголосовать опред.сессии"),
        ])
        
        await self.dp.start_polling(self.bot)

    async def start_handler(self, message: types.Message):
        if str(message.from_user.id) in str(settings.ADMIN_UID):
            await message.reply("Привет, админ! Я бот для голосования. Используй /vote <номер_карты> для голосования.")
        else:
            await message.reply("У вас нет доступа к этому боту.")

    async def vote_handler(self, message: types.Message):
        if str(message.from_user.id) not in str(settings.ADMIN_UID):
            await message.reply("У вас нет доступа к этой команде.")
            return

        try:
            _, card_input = message.text.split(maxsplit=1)
            await message.reply(f"Голосование за карту(ы) {card_input} выполнено для всех сессий.")
            await vote_card_for_all_tappers(card_input)
        except ValueError:
            await message.reply("Неправильный формат команды. Используйте /vote <номер_карты> или /vote <номер_карты1,номер_карты2>")

    async def vote_tapper_handler(self, message: types.Message):
        if str(message.from_user.id) not in str(settings.ADMIN_UID):
            await message.reply("У вас нет доступа к этой команде.")
            return
        
        try:
            _, session_name, card_input = message.text.split(maxsplit=2)
            await message.reply(f"Команда выполнена для сессии {session_name} с картой(ами) {card_input}.")
            await vote_card_for_tapper_by_name(session_name, card_input)
        except ValueError:
            await message.reply("Неправильный формат команды. Используйте /vote_tapper <имя_сессии> <номер_карты> или /vote_tapper <имя_сессии> <номер_карты1,номер_карты2>")
            
    async def list_tappers_handler(self, message: types.Message):
        if str(message.from_user.id) not in str(settings.ADMIN_UID):
            await message.reply("У вас нет доступа к этой команде.")
            return
        
        tapper_list = "\n".join(tapper_instances.keys())
        cleaned_list = tapper_list.encode('utf-8', errors='ignore').decode('utf-8')
        await message.reply(f"Список активных тапперов:\n{cleaned_list}")

async def run_bot():
    if settings.BOT_TOKEN is None and settings.ADMIN_UID is None:
        return
    
    bot = TelegramBot(settings.BOT_TOKEN)
    await bot.start()