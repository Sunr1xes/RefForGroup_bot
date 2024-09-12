import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from config import API_KEY
from handlers.user_profile import profile_handler, history_of_withdrawal, money_withdrawal, slow_withdrawal, instant_withdrawal, enter_instant_withdrawal, back_in_profile, enter_slow_withdrawal, NavigationForProfile
from handlers.help import help_handler, user_agreement_callback_handler
from referral_system import referral_callback_handler, referrals_handler, back_in_referral
from handlers.registration import contact_handler, process_full_name, start_command, Registration
from handlers.admin_menu import admin_menu, change_balance, change_balance_command, delete_user_command, process_delete_user, AdminMenu, list_transactions, approve_transaction, cancel_transaction, back_in_admin_menu, blacklist_user, blacklist_user_command, unblock_user_command, unblock_user
from check_user_in_group import process_check_membership
from membership import CheckUserMiddleware
from handlers.available_work import track_vacancies, show_vacancies, change_page

#TODO сделать сотрудничество, правила, связь с админами и тд (работодатель, человек который будет приводить людей)
#TODO сделать предложить идею
#TODO на потом: можно сделать типо заработок за продвижение, например 50 рублей за историю или еще что-нибудь

# Логирование
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_KEY)  # type: ignore
storage = MemoryStorage()
dp = Dispatcher(bot=bot, storage=storage)

dp.message.middleware(CheckUserMiddleware())
dp.callback_query.middleware(CheckUserMiddleware())

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
router.callback_query.register(blacklist_user, F.data == "blacklist_user")
router.callback_query.register(unblock_user, F.data == "unblock_user")

# Обработчик вывода средств и вывода истории
router.callback_query.register(history_of_withdrawal, F.data.startswith("history_of_withdrawal")  | F.data.startswith("history_page_"))
router.callback_query.register(money_withdrawal, F.data == "money_withdrawal")
router.callback_query.register(slow_withdrawal, F.data == "slow_withdrawal")
router.callback_query.register(instant_withdrawal, F.data == "instant_withdrawal")

# Регистрация обработчиков для состояний регистрации
router.message.register(process_full_name, Registration.waiting_for_full_name)  # Регистрация обработчика для ввода ФИО
router.message.register(contact_handler, Registration.waiting_for_contact)    # Регистрация обработчика для ввода контакта

# Обработчики для вывода средств
router.message.register(enter_instant_withdrawal, NavigationForProfile.instant_withdrawal)
router.message.register(enter_slow_withdrawal, NavigationForProfile.slow_withdrawal)

# Обработчики для админских функций
router.message.register(change_balance_command, AdminMenu.change_balance)
router.message.register(delete_user_command, AdminMenu.delete_user)
router.message.register(blacklist_user_command, AdminMenu.blacklist_user)
router.message.register(unblock_user_command, AdminMenu.unblock_user)
router.callback_query.register(list_transactions, F.data == "transactions")
router.callback_query.register(approve_transaction, F.data.startswith("approve_"))
router.callback_query.register(cancel_transaction, F.data.startswith("cancel_"))
router.callback_query.register(back_in_admin_menu, F.data == "back_in_admin_menu", StateFilter("*"))

# Обработчик кнопки "Доступная работа"
router.message.register(track_vacancies,F.chat.type.in_(['group', 'supergroup']) & F.text.contains("#вакансия"))
router.callback_query.register(change_page, F.data.startswith("vacancy_page_"))

# Обработчик кнопки "cancel"
router.callback_query.register(back_in_profile, F.data == "back_in_profile", StateFilter("*"))
router.callback_query.register(back_in_referral, F.data == "back_in_referral", StateFilter("*"))

async def main():
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
