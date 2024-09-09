import logging
import re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Vacancy, get_async_session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from membership import check_membership

router = Router()

class NavigationVacancies(StatesGroup):
    vacancies = State()


back_button = InlineKeyboardButton(text="Назад", callback_data="back_vacancies_to_profile")

@router.message(F.chat.type.in_(['group', 'supergroup']) & F.text.contains("#вакансия"))
async def track_vacancies(message: Message):
    """
    Функция для отслеживания сообщений с хэштегом #вакансия из чатов.
    """
    vacancy_text = re.sub(r"#вакансия", "", message.text)  # type: ignore # Убираем хештег #вакансия
    vacancy_text = vacancy_text.strip()  # Убираем лишние пробелы в начале и конце текста
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

@router.callback_query(NavigationVacancies.vacancies)
async def show_vacancies(callback_query: CallbackQuery, state: FSMContext):
    bot = callback_query.bot
    page = 1

    if callback_query.data.startswith("vacancy_page_"):  # type: ignore # Проверка страницы
        page = int(callback_query.data.split("_")[2])  # type: ignore # Получаем номер страницы из callback_data

    items_per_page = 5  # Количество вакансий на странице

    # Удаляем предыдущее сообщение с клавиатурой
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore

    # Проверка членства пользователя
    if not await check_membership(bot, callback_query): # type: ignore
        return

    async with get_async_session() as db:
        try:
            result = await db.execute(select(Vacancy).filter_by(status='active').order_by(desc(Vacancy.created_at)))
            vacancies = result.scalars().all()

            total_vacancies = len(vacancies)
            start = (page - 1) * items_per_page
            end = start + items_per_page
            vacancies_page = vacancies[start:end]

            # Формирование текста вакансий
            vacancies_text = "📋 *Доступные вакансии:*\n\n"
            vacancies_info = "\n\n──────────\n\n".join(
                [f"🔹 *ID:* {vacancy.id}\n"
                 f"💼 *Описание:* {vacancy.text.strip()}\n"
                 f"📅 *Дата добавления:* {vacancy.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                 for vacancy in vacancies_page]) or "🔹 Вакансий пока нет."

            # Клавиатура для переключения страниц
            buttons = []

            # Кнопка "Назад", если это не первая страница
            if page > 1:
                buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"vacancy_page_{page - 1}"))

            # Кнопка "Вперед", если есть больше вакансий на следующей странице
            if end < total_vacancies:
                buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"vacancy_page_{page + 1}"))

            # Клавиатура с кнопками
            inline_kb = InlineKeyboardMarkup(inline_keyboard=[buttons, [back_button]])

            # Проверка, отличается ли новый текст от текущего сообщения
            if callback_query.message.text != vacancies_text or callback_query.message.reply_markup != inline_kb: # type: ignore
                # Обновляем сообщение только если текст или клавиатура изменились
                await callback_query.message.edit_text(vacancies_text + vacancies_info, parse_mode="Markdown", reply_markup=inline_kb) # type: ignore
            else:
                # Сообщение и клавиатура те же самые, нет необходимости обновлять
                await callback_query.answer("Ничего не изменилось", show_alert=False)

            await state.set_state(NavigationVacancies.vacancies)

        except SQLAlchemyError as e:
            logging.error(f"Ошибка получения списка вакансий: {e}")
            await callback_query.message.answer("🚫 Произошла ошибка при получении списка вакансий.")
