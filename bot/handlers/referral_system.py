import logging
import re
from config import REFERRAL_PERCENTAGE
from database import get_async_session, User, Referral
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from membership import check_membership

#TODO получше разобраться с работой рефералов и сделать наглядно сколько с каждого заработал
#TODO мб мб сделать как в скрудже донат команде со списком лучших и тд)) 
#TODO доделать кнопки скопировать ссылку и пригласить друзей

router = Router()

class ReferralSystem:

    @staticmethod
    async def get_users_referrals(user_id: int):
        async with get_async_session() as db:
            try:
                result = await db.execute(select(User).filter(User.user_id == user_id))
                db_user = result.scalar_one_or_none()
            
                if db_user:
                    result = await db.execute(
                        select(User)
                        .join(Referral, User.id == Referral.referral_id)
                        .filter(Referral.user_id == db_user.id)
                    )
                    referrals = result.scalars().all()
                    return referrals
                else:
                    return None
            except SQLAlchemyError as e:
                logging.error(f"Failed to get referrals: {user_id}. Error: {e}")
                return None


    @staticmethod
    async def add_referral(referrer_id: int, referral_id: int):
        async with get_async_session() as db:
            try:
                new_referral = Referral(user_id=referrer_id, referral_id=referral_id)
                db.add(new_referral)
                await db.commit()
                return True
            except SQLAlchemyError as e:
                await db.rollback()
                logging.error(f"Failed to add referral: {referrer_id} -> {referral_id}. Error: {e}")
                return False
            
    @staticmethod
    async def process_referral(user_id: int, referrer_id: int):
        """
        Обрабатывает реферальную ссылку. Добавляет пользователя как реферала к рефереру,
        если реферер существует, и пользователь еще не зарегистрирован как реферал.
        """
        async with get_async_session() as db:
            try:
                # Проверяем, существует ли реферер
                result = await db.execute(select(User).filter(User.user_id == referrer_id))
                referrer = result.scalar_one_or_none()

                if not referrer:
                    return False, "❗ Некорректная реферальная ссылка."

                # Проверяем, не существует ли уже запись реферала
                result = await db.execute(select(Referral).filter(Referral.referral_id == user_id))
                existing_referral = result.scalar_one_or_none()

                if existing_referral:
                    return False, "❗ Вы уже зарегистрированы как реферал."

                # Создание новой записи реферала
                new_referral = Referral(user_id=referrer.id, referral_id=user_id)
                db.add(new_referral)
                await db.commit()

                return True, "🎉 Реферальная ссылка успешно обработана!"

            except SQLAlchemyError as e:
                await db.rollback()
                logging.error(f"Ошибка при обработке реферальной ссылки: {e}")
                return False, "⚠️ Ошибка при обработке реферальной системы."

            

@router.message(F.text == "🫂 Рефералы")
async def referrals_handler(message: Message):
    """
    Обрабатывает команду показа списка рефералов пользователя.
    """

    bot = message.bot
    user_id = message.from_user.id  # type: ignore

    if not await check_membership(bot, message):  # type: ignore
        return

    async with get_async_session() as db:
        # Выполняем объединенный запрос для получения пользователя и его рефералов
        result = await db.execute(
            select(User, Referral).join(Referral, Referral.user_id == User.id, isouter=True).filter(User.user_id == user_id)
        )
        data = result.fetchall()
        db_user = data[0][0]  # Данные пользователя

        # Получаем список рефералов
        referrals = [referral for _, referral in data if referral]

        if referrals:
            # Формируем список рефералов
            referral_list = "\n".join([f"👤 {referral.first_name_tg} (ID: {referral.user_id})" for referral in referrals])
            earnings_info = f"💸 *Заработок с рефералов:* {db_user.referral_earnings} рублей."  # type: ignore
            response_text = (
                f"🫂 *Ваши рефералы:*\n\n"
                f"{referral_list}\n\n"
                f"{earnings_info}\n\n"
                "Продолжайте приглашать друзей, чтобы зарабатывать больше!"
            )
        else:
            response_text = (
                "🫂 *Ваши рефералы:*\n\n"
                "У вас пока нет рефералов.\n\n"
                "Приглашайте друзей, чтобы заработать с каждого приглашенного!"
            )

    # Добавляем кнопку генерации ссылки
    generate_referral_url_button = InlineKeyboardButton(text="🔗 Сгенерировать пригласительную ссылку", callback_data="generate_referral_url")
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[generate_referral_url_button]])

    await message.answer(response_text, reply_markup=inline_kb, parse_mode="Markdown")



@router.callback_query(F.data == "generate_referral_url")
async def referral_callback_handler(callback_query: CallbackQuery):
    """
    Обрабатывает нажатие на кнопку "Сгенерировать пригласительную ссылку".
    """
    user_id = callback_query.from_user.id  # type: ignore
    bot_username = (await callback_query.bot.get_me()).username  # type: ignore
    referral_link = f"https://t.me/{bot_username}?start={user_id}"

    # Создание кнопок для действий с реферальной ссылкой
    copy_button = InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data="copy_referral_link")
    invite_button = InlineKeyboardButton(text="👥 Пригласить друзей", url=referral_link)

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[copy_button], [invite_button]])

    # Красивый вывод сообщения с ссылкой и инструкциями
    referral_text = (
        "🎉 *Поздравляем!* 🎉\n\n"
        "Ваша персональная реферальная ссылка готова!\n\n"
        f"🔗 *Ваша реферальная ссылка:*\n`{referral_link}`\n\n"
        "Отправьте эту ссылку своим друзьям и получите бонусы за их регистрацию!\n\n"
        "👥 Чем больше друзей вы пригласите, тем больше бонусов вы получите!"
    )

    await callback_query.message.answer(referral_text, parse_mode="Markdown", reply_markup=inline_kb)  # type: ignore
    await callback_query.answer()  # Подтверждение обработки callback