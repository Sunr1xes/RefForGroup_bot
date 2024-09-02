import logging
from aiogram import Bot, types
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import Message
from config import GROUP_CHAT_ID, ADMIN_MAKSIM, ADMIN_ROMAN
from asyncio.log import logger
import aiofiles

async def check_membership(bot: Bot, message: Message) -> bool:
    """
    Проверяет, находится ли пользователь в чате.
    Если нет, отправляет сообщение с просьбой присоединиться к чату.
    
    :param bot: Инстанс бота
    :param message: Сообщение пользователя
    :return: True, если пользователь в чате, False если нет
    """
    user_id = message.from_user.id # type: ignore
    try:
        member = await bot.get_chat_member(GROUP_CHAT_ID, user_id) # type: ignore
        if member.status in ['member', 'administrator', 'creator']:
            return True
        else:
            link_on_group = InlineKeyboardButton(text="Вступить в чат", url="https://t.me/+PKddIYAM4so5MzNi")
            check_user_in_group = InlineKeyboardButton(text="Проверить", callback_data="check_user_in_group")
            inline_kb = InlineKeyboardMarkup(inline_keyboard=[[link_on_group], [check_user_in_group]])
            await message.answer("Для использования бота вам необходимо вступить в [чат](https://t.me/+PKddIYAM4so5MzNi)", 
                                 parse_mode="Markdown", 
                                 disable_web_page_preview=True, 
                                 reply_markup=inline_kb
                                )
            return False
    except Exception as e:
        logger.error(f"Error checking user status in chat: {e}")
        await message.answer("Произошла ошибка при проверке вашего статуса в чате. Пожалуйста, попробуйте позже.")
        return False


async def prompt_for_registration(message: Message):
    contact_button = KeyboardButton(text="Отправить номер телефона", request_contact=True)
    keyboard = ReplyKeyboardMarkup(keyboard=[[contact_button]], resize_keyboard=True)
    await message.answer("Нажми на кнопку, чтобы зарегистрироваться.", reply_markup=keyboard)

async def is_user_in_chat(bot: Bot, group_chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(group_chat_id, user_id)
        return member.status not in ['left', 'kicked']
    except Exception as e:
        logger.error(f"Error checking user status in chat: {e}")
        return False

async def load_user_agreement():
    async with aiofiles.open("user_agreement.txt", "r", encoding="utf-8") as file:
        return await file.read()


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
    await message.answer("Выберите действие:", reply_markup=menu_keyboard, input_field_placeholder="Выберите действие:")


async def is_admins(user_id: int) -> bool:
    is_admin = user_id in [int(ADMIN_ROMAN), int(ADMIN_MAKSIM)]
    logging.info(f"is_admins check: user_id={user_id}, is_admin={is_admin}")
    return is_admin
