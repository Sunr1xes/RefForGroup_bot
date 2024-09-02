import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
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
router.message.register(admin_menu, Command("admin_menu"))
router.message.register(contact_handler, F.content_type == "contact")
router.message.register(profile_handler, F.text == "Профиль👤")
router.message.register(referrals_handler, F.text == "Рефералы🫂")
router.message.register(help_handler,F.text == "Помощь🆘")


router.callback_query.register(referral_callback_handler, F.data == "generate_referral_url")
router.callback_query.register(process_check_membership, F.data == "check_user_in_group")
router.callback_query.register(user_agreement_callback_handler, F.data == "user_agreement")
router.callback_query.register(change_balance, F.data == "change_balance")
router.callback_query.register(process_delete_user, F.data == "delete_user")

#Обработчики для админских функций
router.callback_query.register(change_balance_command, F.data == "change_balance")
router.callback_query.register(delete_user_command, F.text.startswith("удалить пользователя"))


async def main():
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())