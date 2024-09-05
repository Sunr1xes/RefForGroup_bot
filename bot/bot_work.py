import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from config import API_KEY
from handlers.profile_1 import profile_handler
from handlers.help import help_handler, user_agreement_callback_handler
from handlers.referral_system import referral_callback_handler, referrals_handler
from handlers.registration import contact_handler, process_full_name, start_command, Registration
from handlers.admin_menu import admin_menu, change_balance, change_balance_command, delete_user_command, process_delete_user, AdminMenu 
from utils import process_check_membership 

#TODO уже сделать "Доступную работу"
#TODO сделать сотрудничество, правила, связь с админами и тд (работодатель, человек который будет приводить людей)
#TODO сделать предложить идею
#TODO на потом: можно сделать типо заработок за продвижение, например 50 рублей за историю или еще что-нибудь


# Логирование
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_KEY)  # type: ignore
storage = MemoryStorage()
dp = Dispatcher(bot=bot, storage=storage)
router = Router()

# Регистрация обработчиков
router.message.register(start_command, Command("start"))
router.message.register(admin_menu, Command("admin_menu"))
router.message.register(help_handler, Command("help"))
router.message.register(contact_handler, F.content_type == "contact")
router.message.register(profile_handler, F.text == "Профиль👤")
router.message.register(referrals_handler, F.text == "Рефералы🫂")
router.message.register(help_handler, F.text == "Помощь🆘")


router.callback_query.register(referral_callback_handler, F.data == "generate_referral_url")
router.callback_query.register(process_check_membership, F.data == "check_user_in_group")
router.callback_query.register(user_agreement_callback_handler, F.data == "user_agreement")
router.callback_query.register(change_balance, F.data == "change_balance")
router.callback_query.register(process_delete_user, F.data == "delete_user")

# Регистрация обработчиков для состояний регистрации
router.message.register(process_full_name, Registration.waiting_for_full_name)  # Регистрация обработчика для ввода ФИО
router.message.register(contact_handler, Registration.waiting_for_contact)    # Регистрация обработчика для ввода контакта

# Обработчики для админских функций
router.message.register(change_balance_command, AdminMenu.change_balance)
router.message.register(delete_user_command, AdminMenu.delete_user)


async def main():
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
