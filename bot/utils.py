import logging
import pytz
from aiogram import Router
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, Message, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from config import ADMIN_MAKSIM, ADMIN_ROMAN, ADMIN_ACCOUNT, BANK_MAP
from database import WithdrawalHistory

router = Router()

async def prompt_for_registration(message: Message):
    """
    Запрашивает у пользователя отправку номера телефона для регистрации.
    """
    # Создаем кнопку для отправки номера телефона
    contact_button = KeyboardButton(text="📞 Отправить номер телефона", request_contact=True)
    keyboard = ReplyKeyboardMarkup(keyboard=[[contact_button]], resize_keyboard=True)

    # Отправляем сообщение с инструкцией
    await message.answer(
        "📱 Пожалуйста, отправьте свой номер телефона, нажав на кнопку ниже.\n"
        "Это необходимо для завершения регистрации. 🔒",
        reply_markup=keyboard
    )

async def menu_handler(message: Message, greeting_text: str):
    # Кнопки с красивыми смайликами для улучшения интерфейса
    profile_keyboard = KeyboardButton(text="👤 Профиль")
    referrals_keyboard = KeyboardButton(text="🫂 Рефералы")
    support_keyboard = KeyboardButton(text="🆘 Помощь")
    work_keyboard = KeyboardButton(text="👷🏻‍♂️ Актуальные вакансии", callback_data="show_vacancies")
    
    # Меню клавиатуры с добавлением смайликов и интуитивных действий
    menu_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [work_keyboard, referrals_keyboard],  # Первый ряд - вакансии и рефералы
            [support_keyboard],  # Второй ряд - помощь
            [profile_keyboard]  # Третий ряд - профиль
        ], 
        resize_keyboard=True
    )
    
    # Удаление предыдущей клавиатуры (если была) и вывод приветственного сообщения
    await message.answer(greeting_text, reply_markup=ReplyKeyboardRemove())
    # Отправка меню с предложением выбрать действие
    await message.answer("📋 *Выберите действие из меню ниже:*", reply_markup=menu_keyboard, parse_mode="Markdown")



async def is_admins(user_id: int) -> bool:
    is_admin = user_id in [int(ADMIN_ROMAN), int(ADMIN_MAKSIM), int(ADMIN_ACCOUNT)] # type: ignore
    logging.info(f"is_admins check: user_id={user_id}, is_admin={is_admin}")
    return is_admin


# Сохраняем предыдущее состояние в каждом меню
async def save_previous_state(state: FSMContext):
    current_state = await state.get_state()
    await state.update_data(previous_state=current_state)

async def send_transaction_list(bot, chat_id, transactions, title):
    """
    Отправляет список транзакций, по одной транзакции на сообщение.
    """
    if not transactions:
        await bot.send_message(chat_id, f"{title}: ✅")
        return

    # Отправляем транзакции по одной
    for txn in transactions:
        transaction_text = (
            f"📋 *{title}*\n\n"
            f"🔹 *ID:* {txn.id}\n"
            f"👨 *Пользователь:* {txn.user.first_name_tg}\n"
            f"👤 *ФИО:* {txn.user.last_name} {txn.user.first_name} {txn.user.patronymic}\n"
            f"💰 *Сумма:* {txn.amount}₽\n"
            f"📅 *Дата:* {txn.withdrawal_date.astimezone(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M')}\n"
        )
        
        approve_button = InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{txn.id}")
        cancel_button = InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{txn.id}")
        txn_keyboard = InlineKeyboardMarkup(inline_keyboard=[[approve_button, cancel_button]])

        # Отправляем сообщение с кнопками для каждой транзакции
        await bot.send_message(chat_id, transaction_text, reply_markup=txn_keyboard, parse_mode="Markdown")


async def get_bank_and_phone(session: AsyncSession, withdrawal_id: int):
    # Выбираем строку description из таблицы WithdrawalHistory
    try:
        result = await session.execute(
            select(WithdrawalHistory).filter(WithdrawalHistory.id == withdrawal_id)
        )
        withdrawal = result.scalar_one_or_none()
        
        if withdrawal:
            description = withdrawal.description
            
            # Извлекаем банк и реквизиты из строки description
            bank_info = description.split(", ")
            bank = bank_info[0].replace("Банк: ", "")
            card_or_phone = bank_info[1].replace("Реквизиты: ", "")
            
            bank = BANK_MAP.get(bank.lower(), bank)  # Используем банк из словаря или как есть
            
            return f"🏦 *Банк:* {bank}\n💳 *Реквизиты:* {card_or_phone}"  # Возвращаем строку, а не кортеж
        return "Информация отсутствует"
    except SQLAlchemyError as e:
        logging.error(f"Error while getting bank and phone: {e}")
        return "Ошибка"
