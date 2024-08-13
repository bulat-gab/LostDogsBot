from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from bot.core.tapper import vote_card_for_all_tappers
from bot.config import settings

class TelegramBot:
    def __init__(self, token: str):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()

    async def start(self):
        self.dp.message(Command("start"))(self.start_handler)
        self.dp.message(Command("vote"))(self.vote_handler)
        await self.dp.start_polling(self.bot)

    async def start_handler(self, message: types.Message):
        if str(message.from_user.id) == settings.ADMIN_UID:
            await message.reply("Привет, админ! Я бот для голосования. Используй /vote <номер_карты> для голосования.")
        else:
            await message.reply("У вас нет доступа к этому боту.")

    async def vote_handler(self, message: types.Message):
        if str(message.from_user.id) != settings.ADMIN_UID:
            await message.reply("У вас нет доступа к этой команде.")
            return

        try:
            _, card_number = message.text.split()
            card_number = int(card_number)
            if 1 <= card_number <= 3:
                await vote_card_for_all_tappers(card_number)
                await message.reply(f"Голосование за карту {card_number} выполнено для всех сессий.")
            else:
                await message.reply("Номер карты должен быть от 1 до 3.")
        except ValueError:
            await message.reply("Неправильный формат команды. Используйте /vote <номер_карты>")

async def run_bot(token: str):
    bot = TelegramBot(token)
    await bot.start()