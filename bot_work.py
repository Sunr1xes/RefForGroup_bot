import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# Подключение API
load_dotenv()
API_KEY = os.getenv("API_KEY")

# Проверка, что API_KEY не None
if API_KEY is None:
    raise ValueError(
        "Переменная окружения API_KEY не установлена. Пожалуйста, проверьте файл .env."
    )

# Логгирование
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_KEY)
dp = Dispatcher()


# Обработчик команды /start
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("Привет! Я бот, как я могу помочь вам сегодня?")


async def main():
    # Регистрация обработчиков
    dp.message.register(send_welcome, Command("start"))

    # Запуск polling
    await bot.delete_webhook(
        drop_pending_updates=True
    )  # Удаление старого вебхука (если был установлен)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
