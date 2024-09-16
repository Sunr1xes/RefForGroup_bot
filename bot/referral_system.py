import logging
from config import REFERRAL_PERCENTAGE
from database import get_async_session, User, Referral
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
import urllib.parse
from utils import save_previous_state
from membership import is_user_blocked, check_membership

#TODO получше разобраться с работой рефералов и сделать наглядно сколько с каждого заработал
#TODO мб мб сделать как в скрудже донат команде со списком лучших и тд)) 

router = Router()

class NavigationForReferral(StatesGroup):
    main_referral_menu = State()
    referral_link = State()

back_button = InlineKeyboardButton(text="Назад", callback_data="back_in_referral")

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
        если реферер существует, и пользователь уже не зарегистрирован как реферал.
        """
        async with get_async_session() as db:
            try:
                # Проверяем, существует ли реферер
                result = await db.execute(select(User).filter(User.user_id == referrer_id))
                referrer = result.scalar_one_or_none()

                if not referrer:
                    return False, "❗ Некорректная реферальная ссылка."

                # Проверяем, зарегистрирован ли пользователь, которого хотят добавить в рефералы
                result = await db.execute(select(User).filter(User.user_id == user_id))
                user = result.scalar_one_or_none()

                if not user:
                    logging.error(f"Пользователь с ID {user_id} не найден в таблице users.")
                    return False, "❗ Пользователь должен быть зарегистрирован перед использованием реферальной ссылки."

                # Проверяем, не существует ли уже запись реферала
                result = await db.execute(select(Referral).filter(Referral.referral_id == user_id))
                existing_referral = result.scalar_one_or_none()

                if existing_referral:
                    return False, "❗ Вы уже зарегистрированы как реферал."

                # Логирование перед созданием записи
                logging.info(f"Добавляем запись о реферале: {referrer.id} -> {user.id}")

                # Создание новой записи реферала
                new_referral = Referral(user_id=referrer.id, referral_id=user.id)
                db.add(new_referral)
                user.referrer_id = referrer.id
                await db.commit()

                return True, "🎉 Реферальная ссылка успешно обработана!"

            except SQLAlchemyError as e:
                await db.rollback()
                logging.error(f"Ошибка при обработке реферальной ссылки: {e}")
                return False, "⚠️ Ошибка при обработке реферальной системы."


@router.message(F.text == "🫂 Рефералы")
async def referrals_handler(message: Message, state: FSMContext):
    """
    Обрабатывает команду показа списка рефералов пользователя.
    """

    if await is_user_blocked(message.from_user.id):  # type: ignore # Проверка на блокировку
        await message.answer("❌ Вы заблокированы и не можете пользоваться ботом.")
        return
    
    if not await check_membership(message.bot, message):  # type: ignore # Проверка на членство в группе
        return  # Пользователь не в группе, дальнейший код не выполняется

    await save_previous_state(state)
    user_id = message.from_user.id  # type: ignore

    async with get_async_session() as db:
        # Запрашиваем пользователя и его рефералов, используя joinedload для явной загрузки связанных данных
        result = await db.execute(
            select(User)
            .options(joinedload(User.referrals).joinedload(Referral.referral_user))  # Загружаем данные о рефералах и связанных пользователях
            .filter(User.user_id == user_id)
        )
        db_user = result.unique().scalar_one_or_none()  # Применяем unique() перед scalar_one_or_none()

        if not db_user:
            await message.answer("❗ Пользователь не найден.")
            return

        referrals = db_user.referrals

        if referrals:
            referral_list = []
            for referral in referrals:
                referral_user = referral.referral_user
                if referral_user:
                    is_blocked = await is_user_blocked(referral_user.user_id)  # type: ignore
                    status = " (заблокирован)" if is_blocked else ""
                    referral_list.append(f"👤 {referral_user.first_name_tg}{status} (ID: {referral_user.user_id}){status}")
                else:
                    referral_list.append(f"Пользователь удален")

            # Формируем список рефералов
            referral_list_text = "\n".join(referral_list)
            earnings_info = f"💸 *Заработок с рефералов:* {db_user.referral_earnings} рублей."
            response_text = (
                f"🫂 *Ваши рефералы:*\n\n"
                f"{referral_list_text}\n\n"
                f"{earnings_info}\n\n"
                f"👷🏻 За каждую отработанную смену вашего реферала вы получаете {int(REFERRAL_PERCENTAGE * 100)}% от суммы сделки.\n\n🤝 Продолжайте приглашать друзей, чтобы зарабатывать больше!"
            )

        else:
            response_text = (
                "🫂 *Ваши рефералы:*\n\n"
                "У вас пока нет рефералов.\n\n"
                f"👷🏻 За каждую отработанную смену вашего реферала вы получаете {int(REFERRAL_PERCENTAGE * 100)}% от суммы сделки.\n\n🤝 Приглашайте друзей, чтобы заработать с каждого приглашенного!"
            )

    # Добавляем кнопку генерации ссылки
    generate_referral_url_button = InlineKeyboardButton(text="🔗 Сгенерировать пригласительную ссылку", callback_data="generate_referral_url")
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[generate_referral_url_button]])

    await state.update_data(last_message=response_text)
    await message.answer(response_text, reply_markup=inline_kb, parse_mode="Markdown")
    await state.set_state(NavigationForReferral.main_referral_menu)



@router.callback_query(F.data == "generate_referral_url")
async def referral_callback_handler(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку "Сгенерировать пригласительную ссылку".
    """
    bot = callback_query.bot
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id) # type: ignore
    encoded_text = urllib.parse.quote("Присоединяйся и зарабатывай вместе со мной!")
    user_id = callback_query.from_user.id  # type: ignore
    bot_username = (await callback_query.bot.get_me()).username  # type: ignore
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    url=f"https://t.me/share/url?url={referral_link}&text={encoded_text}"

    # Создание кнопок для действий с реферальной ссылкой
    invite_button = InlineKeyboardButton(text="👥 Пригласить друзей", url=url)

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[invite_button], [back_button]])

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
    await state.set_state(NavigationForReferral.referral_link)

@router.callback_query(F.data == "back_in_referral", StateFilter("*"))
async def back_in_referral(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_message = data.get("last_message")

    if not last_message:
        last_message = "Профиль не найден. Пожалуйста, перезапустите бота."

    current_state = await state.get_state()

    if current_state == NavigationForReferral.referral_link.state:
        # Создание кнопки и клавиатуры
        referral_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Сгенерировать пригласительную ссылку", callback_data="generate_referral_url")]
        ])

        await callback_query.message.edit_text( # type: ignore
            text=last_message,
            reply_markup=referral_keyboard,  # Исправленный вызов
            parse_mode="Markdown"
        )
        # Устанавливаем новое состояние
        await state.set_state(NavigationForReferral.main_referral_menu)
    else:
        await callback_query.message.answer("Что-то пошло не так. Пожалуйста, попробуйте позже.")  # type: ignore
        await state.clear()  # Очищаем состояние, если что-то пошло не так