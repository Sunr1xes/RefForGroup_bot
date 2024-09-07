import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from config import API_KEY
from handlers.user_profile import profile_handler, history_of_withdrawal, money_withdrawal, slow_withdrawal, instant_withdrawal, enter_instant_withdrawal, back, NavigationForProfile
from handlers.help import help_handler, user_agreement_callback_handler
from handlers.referral_system import referral_callback_handler, referrals_handler
from handlers.registration import contact_handler, process_full_name, start_command, Registration
from handlers.admin_menu import admin_menu, change_balance, change_balance_command, delete_user_command, process_delete_user, AdminMenu 
from utils import process_check_membership
from handlers.available_work import track_vacancies, show_vacancies

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

# Регистрация обработчиков и меню
router.message.register(start_command, Command("start"))
router.message.register(admin_menu, Command("admin_menu"))
router.message.register(help_handler, Command("help"))
router.message.register(contact_handler, F.content_type == "contact")
router.message.register(profile_handler, F.text == "👤 Профиль")
router.message.register(referrals_handler, F.text == "🫂 Рефералы")
router.message.register(help_handler, F.text == "🆘 Помощь")
router.message.register(show_vacancies, F.text == "👷🏻‍♂️ Актуальные вакансии")

# Обработчик вспомогательных функций (кнопок)
router.callback_query.register(referral_callback_handler, F.data == "generate_referral_url")
router.callback_query.register(process_check_membership, F.data == "check_user_in_group")
router.callback_query.register(user_agreement_callback_handler, F.data == "user_agreement")

# Обработчик админки
router.callback_query.register(change_balance, F.data == "change_balance")
router.callback_query.register(process_delete_user, F.data == "delete_user")

# Обработчик вывода средств и вывода истории
router.callback_query.register(history_of_withdrawal, F.data == "history_of_withdrawal")
router.callback_query.register(money_withdrawal, F.data == "money_withdrawal")
router.callback_query.register(slow_withdrawal, F.data == "slow_withdrawal")
router.callback_query.register(instant_withdrawal, F.data == "instant_withdrawal")

# Регистрация обработчиков для состояний регистрации
router.message.register(process_full_name, Registration.waiting_for_full_name)  # Регистрация обработчика для ввода ФИО
router.message.register(contact_handler, Registration.waiting_for_contact)    # Регистрация обработчика для ввода контакта

# Обработчики для вывода средств
router.message.register(enter_instant_withdrawal, NavigationForProfile.instant_withdrawal)

# Обработчики для админских функций
router.message.register(change_balance_command, AdminMenu.change_balance)
router.message.register(delete_user_command, AdminMenu.delete_user)

# Обработчик кнопки "Доступная работа"
router.message.register(track_vacancies,F.chat.type.in_(['group', 'supergroup']) & F.text.contains("#вакансия"))
router.message.register(show_vacancies, F.text.contains("Доступная работа👷🏻‍♂️"))

# Обработчик кнопки "cancel"
router.callback_query.register(back, F.data == "back", StateFilter("*"))

async def main():
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
