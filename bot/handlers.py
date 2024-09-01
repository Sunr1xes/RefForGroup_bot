from asyncio.log import logger
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, Message, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database import User, get_db, Referral
from config import GROUP_CHAT_ID
from utils import *


#TODO сделать чтоб при нажатии на кнопку шла сначала проверка на то что человек в группе
router = Router()

@router.message(Command("start"))
async def start_command(message: Message):
    bot = message.bot

    if not await check_membership(bot, message): # type: ignore
        return
    
    user_id = message.from_user.id # type: ignore
    args = message.text.split()[1:] # type: ignore

    db: Session = next(get_db())
    db_user = db.query(User).filter(User.user_id == user_id).first()

    if await is_user_in_chat(bot, GROUP_CHAT_ID, user_id): # type: ignore
        if db_user:
            await menu_handler(message, "Добро пожаловать!")
        else:
            await prompt_for_registration(message)
    else:
        await message.answer("Привет! Для использования бота вам необходимо вступить в [чат](https://t.me/+PKddIYAM4so5MzNi)", parse_mode="Markdown")
        return

    if args and not db_user:
        try:
            referrer_user_id = int(args[0])
            referrer_user = db.query(User).filter(User.user_id == referrer_user_id).first()

            if referrer_user:
                existing_referral = db.query(Referral).filter(Referral.referral_id == user_id).first()
                if existing_referral:
                    await message.answer("Вы уже зарегистрированы.")
                    return
                
                new_referral = Referral(user_id=referrer_user.id, referrer_id = user_id)
                db.add(new_referral)
                try:
                    db.commit()
                    logger.info(f"User {user_id} was referred by {referrer_user.user_id}")
                except SQLAlchemyError as e:
                    db.rollback()
                    logger.error(f"Error saving referral to database: {e}")
                    await message.answer("Произошла ошибка при обработке реферальной системы, попробуйте позже или обратитесь в поддержку.")
            else:
                await message.answer("Некорректная реферальная ссылка")
        except ValueError:
            await message.answer("Некорректная реферальная ссылка")
    elif not args:
        if not db_user:
            await prompt_for_registration(message)

@router.message(F.content_type == "contact")
async def contact_handler(message: Message):

    bot = message.bot
    user_id = message.from_user.id # type: ignore

    if not await is_user_in_chat(bot, GROUP_CHAT_ID, user_id): # type: ignore
        await message.answer("Вы не вступили в чат.")
        return

    contact = message.contact

    if contact is None:
        await message.answer("Контактные данные не были переданы.")
        return
    
    user_name = contact.first_name or ""
    last_user_name = contact.last_name or ""
    phone_number = contact.phone_number or ""
    user_id = message.from_user.id # type: ignore

    db: Session = next(get_db())
    db_user = db.query(User).filter(User.user_id == user_id).first()
    
    if not db_user:
        new_user = User(
            user_id=user_id,
            first_name=user_name,
            last_name=last_user_name,
            phone_number=phone_number
        )
        db.add(new_user)
        try:
            db.commit()
            await menu_handler(message, "Спасибо, регистрация прошла успешно!")
            logger.info(f"User {user_name} with ID {user_id} has been added to the database.")
        except SQLAlchemyError as e:
            db.rollback()
            await message.answer("Произошла ошибка при регистрации, попробуйте позже.")
            logger.error(f"Error saving user to database: {e}")
    else:
        await menu_handler(message, "Вы уже зарегистрированы.")


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

@router.message(F.text == "Профиль👤")
async def profile_handler(message: Message):
    bot = message.bot

    if not await check_membership(bot, message): # type: ignore
        return

    user_id = message.from_user.id # type: ignore
    db: Session = next(get_db())

    db_user = db.query(User).filter(User.user_id == user_id).first()

    if db_user:
        profile_info = (
            f"👤 *Ваш профиль:*\n\n"
            f"Имя: {db_user.first_name}\n"
            f"ID: {db_user.user_id}\n"
            f"Общий заработок: {db_user.referral_earnings}\n"
            f"Баланс на аккаунте: {db_user.account_balance}\n"
        )
        await message.answer(profile_info, parse_mode="Markdown")
    else:
        await message.answer("Ошибка. Ваш профиль не найден. Перезапустите бота с помощью /start")

@router.message(F.text == "Рефералы🫂")
async def referrals_handler(message: Message):
    bot = message.bot

    if not await check_membership(bot, message): # type: ignore
        return

    user_id = message.from_user.id # type: ignore
    db: Session = next(get_db())

    db_user = db.query(User).filter(User.user_id == user_id).first()

    if db_user:
        referrals = db.query(User).join(Referral, User.id == Referral.referral_id).filter(Referral.user_id == db_user.id).all()

        if referrals:
            # Формируем список рефералов
            referral_list = "\n".join([f"{referral.first_name} (ID: {referral.user_id})" for referral in referrals])
            earnings_info = f"💸 Вы заработали с рефералов: {db_user.referral_earnings} рублей." # type: ignore
            response_text = (
                f"🫂 *Ваши рефералы:*\n\n"
                f"{referral_list}\n\n"
                f"{earnings_info}"
            )
        else:
            response_text = "У вас пока нет рефералов."

        generate_referral_url_button = InlineKeyboardButton(text="Сгенерировать пригласительную ссылку🔗", callback_data="generate_referral_url")
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[[generate_referral_url_button]])
    
        await message.answer(response_text, reply_markup=inline_kb, parse_mode="Markdown")
    else:
        await message.answer("Ошибка. Ваш профиль не найден. Перезапустите бота с помощью /start")

@router.callback_query()
async def referral_callback_handler(callback_query: types.CallbackQuery):
    if callback_query.data == "generate_referral_url":
        user_id = callback_query.from_user.id  # type: ignore
        bot_username = (await callback_query.bot.me()).username # type: ignore
        referral_link = f"https://t.me/{bot_username}?start={user_id}"

        await callback_query.message.answer(f"Ваша реферальная ссылка:\n{referral_link}") # type: ignore
    
    await callback_query.answer()  # Подтверждение обработки callback

@router.callback_query(lambda callback_query: callback_query.data == "check_user_in_group")
async def process_check_membership(callback_query: types.CallbackQuery):
    bot = callback_query.bot
    user_id = callback_query.from_user.id  # type: ignore

    # Проверяем, состоит ли пользователь в группе
    member = await bot.get_chat_member(GROUP_CHAT_ID, user_id)
    if member.status in ['member', 'administrator', 'creator']:
        await callback_query.message.edit_text("Спасибо, что вступили в группу! Теперь вы можете продолжить.")
        await prompt_for_registration(callback_query.message)  # Или другое действие, которое нужно выполнить после проверки
    else:
        await callback_query.answer("Вы еще не вступили в группу. Пожалуйста, вступите и попробуйте снова.", show_alert=True)
