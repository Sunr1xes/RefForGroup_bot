import logging
import re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest 
from database import Vacancy, get_async_session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from membership import is_user_blocked, check_membership

router = Router()

class NavigationVacancies(StatesGroup):
    vacancies = State()

@router.message(F.chat.type.in_(['group', 'supergroup']) & F.text.contains("#вакансия"))
async def track_vacancies(message: Message):
    """
    Функция для отслеживания сообщений с хэштегом #вакансия из чатов.
    """
    vacancy_text = re.sub(r"#вакансия", "", message.text).strip()  # type: ignore Убираем лишние пробелы в начале и конце текста
    async with get_async_session() as session:
        try:
            # Сохраняем сообщение с вакансией в базе данных
            await add_vacancy(session, message.chat.id, message.message_id, vacancy_text)
            logging.info(f"Вакансия добавлена из чата {message.chat.id}: {vacancy_text}")
        except SQLAlchemyError as e:
            logging.error(f"Ошибка при добавлении вакансии: {str(e)}")


async def add_vacancy(db, chat_id, message_id, text):
    new_vacancy = Vacancy(
        chat_id=chat_id,
        message_id=message_id,
        text=text
    )
    db.add(new_vacancy)
    await db.commit()

@router.message(F.text == "👷🏻‍♂️ Актуальные вакансии")
async def show_vacancies(message: Message, state: FSMContext, page: int = 1):

    if await is_user_blocked(message.from_user.id):  # type: ignore # Проверка на блокировку
        await message.answer("❌ Вы заблокированы и не можете пользоваться ботом.")
        return
    
    if not await check_membership(message.bot, message):  # type: ignore # Проверка на членство в группе
        return  # Пользователь не в группе, дальнейший код не выполняется

    items_per_page = 3  # Количество вакансий на странице

    async with get_async_session() as db:
        try:
            result = await db.execute(select(Vacancy).filter_by(status='active').order_by(Vacancy.posted_at))
            vacancies = result.scalars().all()

            total_vacancies = len(vacancies)
            start = (page - 1) * items_per_page
            end = start + items_per_page
            vacancies_page = vacancies[start:end]

            # Формирование текста вакансий
            vacancies_text = "📋 *Доступные вакансии:*\n\n"
            vacancies_info = "\n\n──────────\n\n".join(
                [f"🔹 *ID:* {vacancy.id}\n"
                 f"💼 *Описание:*\n\n {vacancy.text.strip()}\n\n"
                 f"📅 *Дата добавления:* {vacancy.posted_at.strftime('%d.%m.%Y %H:%M')}\n"
                 for vacancy in vacancies_page]) or "🔹 Вакансий пока нет."

            # Кнопки "Вперед" и "Назад"
            keyboard_buttons = []
            if page > 1:
                keyboard_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"vacancy_page_{page - 1}"))
            if end < total_vacancies:
                keyboard_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"vacancy_page_{page + 1}"))

            inline_kb = InlineKeyboardMarkup(inline_keyboard=[keyboard_buttons], resize_keyboard=True)

            data = await state.get_data()
            last_message_id = data.get('last_message_id')
            if last_message_id:
                try:
                    await message.bot.delete_message(message.chat.id, last_message_id)  # type: ignore
                except TelegramBadRequest:
                    pass

            new_message = await message.answer(vacancies_text + vacancies_info, parse_mode="Markdown", reply_markup=inline_kb)
            await state.update_data(last_message_id=new_message.message_id)

            # Обновляем состояние страницы
            await state.update_data(page=page)

        except SQLAlchemyError as e:
            logging.error(f"Ошибка получения списка вакансий: {e}")
            await message.answer("🚫 Произошла ошибка при получении списка вакансий.")  # type: ignore


# Обработчик для кнопок "Вперед" и "Назад"
@router.callback_query(F.data.startswith("vacancy_page_"))
async def change_page(callback_query: CallbackQuery, state: FSMContext):

    bot = callback_query.bot

    # Удаляем предыдущее сообщение с вакансией
    data = await state.get_data()
    last_message_id = data.get('last_message_id')
    if last_message_id:
        await bot.delete_message(callback_query.message.chat.id, last_message_id) # type: ignore

    # Извлекаем номер страницы из callback_data
    page = int(callback_query.data.split("_")[-1]) # type: ignore
    
    # Получаем текущее сообщение, чтобы обновить его
    await show_vacancies(callback_query.message, state, page)

    # Подтверждаем callback, чтобы не висел "часик" на кнопке
    await callback_query.answer()

