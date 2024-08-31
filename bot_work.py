import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router
from config import API_KEY
from handlers import start_command, contact_handler

# Логгирование
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_KEY)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Регистрация обработчиков
router.message.register(start_command, Command("start"))
router.message.register(contact_handler, F.content_type == "contact")

async def main():
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())