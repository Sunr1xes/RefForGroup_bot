from asyncio.log import logger
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, Message, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database import User, get_db, Referral
from config import GROUP_CHAT_ID
from utils import *

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
                
                new_referral = Referral(user_id=referrer_user.id, referral_id = user_id)
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

        await callback_query.message.answer(f"Ваша реферальная ссылка:\n`{referral_link}`", parse_mode="Markdown") # type: ignore
    
    await callback_query.answer()  # Подтверждение обработки callback

@router.callback_query(lambda callback_query: callback_query.data == "check_user_in_group")
async def process_check_membership(callback_query: types.CallbackQuery):
    bot = callback_query.bot
    user_id = callback_query.from_user.id  # type: ignore

    # Проверяем, состоит ли пользователь в группе
    member = await bot.get_chat_member(GROUP_CHAT_ID, user_id)
    if member.status in ['member', 'administrator', 'creator']:
        await callback_query.message.edit_text("Спасибо, что вступили в группу! Теперь вы можете продолжить.")
        await menu_handler(callback_query.message)
    else:
        await callback_query.answer("Вы еще не вступили в группу. Пожалуйста, вступите и попробуйте снова.", show_alert=True)

@router.message(F.text == "Помощь🆘")
async def help_handler(message: Message):
    bot = message.bot

    if not await check_membership(bot, message): # type: ignore
        return

    help_text = (
        "👋 Добро пожаловать в бота!\n\n"
        "Вот список доступных команд и функций:\n\n"
        "🔸 /start - Начать взаимодействие с ботом\n"
        "🔸 Профиль👤 - Посмотреть ваш профиль и статус\n"
        "🔸 Рефералы🫂 - Управление вашими рефералами\n"
        "🔸 Доступная работа💸 - Посмотреть доступные вакансии\n\n"
        "Если у вас возникли вопросы, свяжитесь с нашей поддержкой: @sss3ddd"
    )

    user_agreement = InlineKeyboardButton(text="Пользовательское соглашение и правила", callback_data="user_agreement")
    user_agreement_inline_kb = InlineKeyboardMarkup(inline_keyboard=[[user_agreement]])
    
    await message.answer(help_text, reply_markup=user_agreement_inline_kb, parse_mode="Markdown")

@router.callback_query(lambda callback_query: callback_query.data == "user_agreement")
async def user_agreement_callback_handler(callback_query: types.CallbackQuery):
    # Путь к файлу на локальной файловой системе
    file_path = "user_agreement.pdf"  # Замените на реальный путь к вашему файлу
    
    # Создание объекта InputFile
    document = FSInputFile(file_path, filename="Пользовательское соглашение.pdf")
    
    # Отправка файла пользователю
    await callback_query.message.answer_document(document) # type: ignore
    await callback_query.answer()


@router.message(Command("admin_menu"))
async def admin_menu(message: types.Message):
    logging.info(f"Admin menu called by user: {message.from_user.id}")
    if not await is_admins(message.from_user.id):
        logging.warning(f"Access denied for user: {message.from_user.id}")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить баланс", callback_data="change_balance")],
        [InlineKeyboardButton(text="Удалить пользователя", callback_data="delete_user")]
    ])

    await message.answer("Панель администратора:", reply_markup=keyboard)
    logging.info(f"Admin menu displayed for user: {message.from_user.id}")


@router.callback_query(lambda callback_query: callback_query.data == "change_balance")
async def change_balance(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Введите ID пользователя и новый баланс в формате: <user_id> <new_balance>")
    await callback_query.answer()

@router.callback_query(lambda callback_query: callback_query.data == "change_balance")
async def change_balance_command(message: types.Message):
    logging.info(f"Received command for changing balance: {message.text}")

    if not await is_admins(message.from_user.id):
        logging.warning(f"Access denied for user {message.from_user.id}")
        return

    args = message.text.split()
    if len(args) != 2:
        await message.answer("Некорректный формат. Используйте: <user_id> <new_balance>")
        return

    try:
        user_id = int(args[0])
        new_balance = float(args[1])
    except ValueError:
        await message.answer("Некорректные данные. Пожалуйста, убедитесь, что вы ввели числовые значения.")
        return

    if new_balance.is_integer():
        new_balance = int(new_balance)

    db: Session = next(get_db())
    db_user = db.query(User).filter(User.user_id == user_id).first()

    if db_user:
        db_user.account_balance = new_balance
        logging.info(f"Changing balance for user {user_id} to {new_balance}")
        try:
            db.commit()
            logging.info(f"Balance changed successfully for user {user_id}")
            await message.answer(f"Баланс пользователя {user_id} успешно изменен на {new_balance}.")
        except Exception as e:
            db.rollback()
            await message.answer("Произошла ошибка при обновлении баланса.")
            logging.error(f"Error committing the change: {e}")
    else:
        await message.answer("Пользователь не найден.")



@router.callback_query(lambda callback_query: callback_query.data == "delete_user")
async def process_delete_user(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Введите ID пользователя для удаления в формате: <user_id>")
    await callback_query.answer()

@router.message()
async def delete_user_command(message: types.Message):
    if not await is_admins(message.from_user.id):
        return

    args = message.text.split()
    if len(args) != 1:
        await message.answer("Некорректный формат. Используйте: <user_id>")
        return

    user_id = int(args[0])

    db: Session = next(get_db())
    db_user = db.query(User).filter(User.user_id == user_id).first()

    if db_user:
        db.delete(db_user)
        try:
            db.commit()
            await message.answer(f"Пользователь {user_id} успешно удален.")
        except:
            db.rollback()
            await message.answer("Произошла ошибка при удалении пользователя.")
    else:
        await message.answer("Пользователь не найден.")