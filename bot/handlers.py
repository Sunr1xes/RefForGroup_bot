from asyncio.log import logger
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, Message, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database import User, get_db, Referral
from config import GROUP_CHAT_ID

router = Router()

@router.message(Command("start"))
async def start_command(message: Message):
    bot = message.bot
    user_id = message.from_user.id # type: ignore

    await message.answer("Привет! Для использования бота вам необходимо вступить в [чат](https://t.me/+PKddIYAM4so5MzNi)", parse_mode="Markdown")

    contact_button = KeyboardButton(text="Отправить номер телефона", request_contact=True)
    keyboard = ReplyKeyboardMarkup(keyboard=[[contact_button]], resize_keyboard=True)
    await message.answer("Нажми на кнопку, чтобы зарегистрироваться.", reply_markup=keyboard)

    if not await is_user_in_chat(bot, GROUP_CHAT_ID, user_id): # type: ignore
        return

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

async def is_user_in_chat(bot: Bot, group_chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(group_chat_id, user_id)
        return member.status not in ['left', 'kicked']
    except Exception as e:
        logger.error(f"Error checking user status in chat: {e}")
        return False

@router.message(F.text == "Профиль👤")
async def profile_handler(message: Message):
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
        bot_username = (await callback_query.bot.me()).username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"

        await callback_query.message.answer(f"Ваша реферальная ссылка:\n{referral_link}")
    
    await callback_query.answer()  # Подтверждение обработки callback