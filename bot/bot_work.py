import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router
from config import API_KEY
from handlers import *

# Логирование
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_KEY) # type: ignore
storage = MemoryStorage()
dp = Dispatcher(bot=bot, storage=storage)
router = Router()

# Регистрация обработчиков
router.message.register(start_command, Command("start"))
router.message.register(contact_handler, F.content_type == "contact")
router.message.register(profile_handler, F.text == "Профиль👤")
router.message.register(referrals_handler, F.text == "Рефералы🫂")


router.callback_query.register(referral_callback_handler, F.data == "generate_referral_url")
router.callback_query(lambda callback_query: callback_query.data == "check_user_in_group")

async def main():
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())