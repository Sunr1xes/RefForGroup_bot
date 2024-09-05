import logging
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from database import User, get_async_session
from membership import check_membership

#TODO добавить кнопки вывода 
#TODO сделать историю выводов

router = Router()

@router.message(F.text == "Профиль👤")
async def profile_handler(message: Message):
    bot = message.bot
    user_id = message.from_user.id # type: ignore

    if not await check_membership(bot, message): # type: ignore
        return

    async with get_async_session() as db:
        try:
            result = await db.execute(select(User).filter(User.user_id == user_id))
            db_user = result.scalar_one_or_none()

            if db_user:
                profile_info = (
                    f"👤 *Ваш профиль:*\n\n"
                    f"Имя: {db_user.first_name_tg}\n"
                    f"ID: {db_user.user_id}\n"
                    f"Общий заработок: {db_user.referral_earnings}\n"
                    f"Баланс на аккаунте: {db_user.account_balance}\n"
                )
                await message.answer(profile_info, parse_mode="Markdown")
            else:
                await message.answer("Ошибка. Ваш профиль не найден. Перезапустите бота с помощью /start")
        except SQLAlchemyError as e:
            logging.error("Ошибка получения пользователя из базы данных: ", e)
