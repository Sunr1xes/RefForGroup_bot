import logging
import pytz
from aiogram import types, Router, F
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from config import GROUP_CHAT_ID, ADMIN_MAKSIM, ADMIN_ROMAN

router = Router()
    
@router.callback_query(F.data == "check_user_in_group")
async def process_check_membership(callback_query: CallbackQuery):
    """
    Обрабатывает проверку, состоит ли пользователь в группу.
    """
    bot = callback_query.bot
    user_id = callback_query.from_user.id  # type: ignore

    # Проверяем, состоит ли пользователь в группе
    member = await bot.get_chat_member(GROUP_CHAT_ID, user_id)  # type: ignore

    if member.status in ['member', 'administrator', 'creator']:
        # Если пользователь состоит в группе
        await callback_query.message.edit_text( # type: ignore
            "🎉 Спасибо, что вступили в группу!\nТеперь вы можете продолжить использование бота. 🚀"
        )  # type: ignore
    else:
        # Если пользователь не состоит в группе
        await callback_query.answer(
            "❗️ Вы ещё не вступили в группу.\n"
            "Пожалуйста, вступите в группу и попробуйте снова.",
            show_alert=True
        )



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
    await message.answer(greeting_text, reply_markup=types.ReplyKeyboardRemove())
    # Отправка меню с предложением выбрать действие
    await message.answer("📋 *Выберите действие из меню ниже:*", reply_markup=menu_keyboard, parse_mode="Markdown")



async def is_admins(user_id: int) -> bool:
    is_admin = user_id in [int(ADMIN_ROMAN), int(ADMIN_MAKSIM)] # type: ignore
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
