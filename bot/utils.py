import logging
from aiogram import types, Router, F
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, Message, CallbackQuery
from config import GROUP_CHAT_ID, ADMIN_MAKSIM, ADMIN_ROMAN
from database import get_async_session, User
from sqlalchemy.future import select 
from handlers.referral_system import ReferralSystem

router = Router()
    
@router.callback_query(F.data == "check_user_in_group")
async def process_check_membership(callback_query: CallbackQuery):

    """Обрабатывает проверку, состоит ли пользователь в группу."""

    bot = callback_query.bot
    user_id = callback_query.from_user.id  # type: ignore

    # Проверяем, состоит ли пользователь в группе
    member = await bot.get_chat_member(GROUP_CHAT_ID, user_id) # type: ignore

    if member.status in ['member', 'administrator', 'creator']:
        await callback_query.message.edit_text("Спасибо, что вступили в группу! Теперь вы можете продолжить.") # type: ignore
    else:
        await callback_query.answer("Вы еще не вступили в группу. Пожалуйста, вступите и попробуйте снова.", show_alert=True)


async def prompt_for_registration(message: Message):
    contact_button = KeyboardButton(text="Отправить номер телефона", request_contact=True)
    keyboard = ReplyKeyboardMarkup(keyboard=[[contact_button]], resize_keyboard=True)
    await message.answer("Теперь отправьте свой номер телефона", reply_markup=keyboard)

async def process_referral(message: Message, referrer_id: int):
    """
    Обрабатывает реферальную ссылку.
    """
    user_id = message.from_user.id # type: ignore

    async with get_async_session() as db:
        result = await db.execute(select(User).filter(User.user_id == user_id))
        db_user = result.scalar_one_or_none()

        if db_user:
            await message.answer("Вы уже зарегистрированы.")
            return

        try:
            referrer_id = int(referrer_id) 
            success, msg = await ReferralSystem.process_referral(user_id, referrer_id)

            if success:
                logging.info(f"Реферальная ссылка обработана для пользователя {user_id}")
            else:
                logging.warning(f"Ошибка при обработке реферальной ссылки для пользователя {user_id}")

            await message.answer(msg)

        except ValueError:
            await message.answer("Некорректная реферальная ссылка.")
        except Exception as e:
            logging.error(f"Failed to process referral: {user_id} -> {referrer_id}. Error: {e}")
            await message.answer("Произошла ошибка при обработке реферальной ссылки. Пожалуйста, попробуйте позже.")

async def menu_handler(message: Message, greeting_text: str):
    profile_keyboard = KeyboardButton(text="Профиль👤")
    referrals_keyboard = KeyboardButton(text="Рефералы🫂")
    support_keyboard = KeyboardButton(text="Помощь🆘")
    work_keyboard = KeyboardButton(text="Доступная работа💸")
    
    menu_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [work_keyboard, referrals_keyboard], 
            [support_keyboard], 
            [profile_keyboard]
        ], 
        resize_keyboard=True
        )
    
    await message.answer(greeting_text, reply_markup=types.ReplyKeyboardRemove())
    await message.answer("Выберите действие:", reply_markup=menu_keyboard, switch_inline_query_current_chat="Выберите действие:")


async def is_admins(user_id: int) -> bool:
    is_admin = user_id in [int(ADMIN_ROMAN), int(ADMIN_MAKSIM)] # type: ignore
    logging.info(f"is_admins check: user_id={user_id}, is_admin={is_admin}")
    return is_admin
