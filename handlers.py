from asyncio.log import logger
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, Message
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database import User, get_db

router = Router()

@router.message(Command("start"))
async def start_command(message: types.Message):
    contact_button = KeyboardButton(text="Отправить номер телефона", request_contact=True)
    keyboard = ReplyKeyboardMarkup(keyboard=[[contact_button]], resize_keyboard=True)
    await message.answer("Привет! Нажми на кнопку, чтобы зарегистрироваться.", reply_markup=keyboard)

@router.message(F.content_type == "contact")
async def contact_handler(message: Message):
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
            await message.answer("Спасибо, регистрация прошла успешно!", reply_markup=types.ReplyKeyboardRemove())
            logger.info(f"User {user_name} with ID {user_id} has been added to the database.")
        except SQLAlchemyError as e:
            db.rollback()
            await message.answer("Произошла ошибка при регистрации, попробуйте позже.")
            logger.error(f"Error saving user to database: {e}")
    else:
        await message.answer("Вы уже зарегистрированы.")