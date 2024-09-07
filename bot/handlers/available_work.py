import logging
import re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from database import Vacancy, get_async_session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select

router = Router()

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

@router.callback_query(F.data == "show_vacancies")
async def show_vacancies(callback_query: CallbackQuery):
    """
    Функция для отображения списка вакансий при нажатии на кнопку.
    """
    if not await check_membership(bot, message):  # type: ignore
        return
    
    async with get_async_session() as db:
        try:
            result = await db.execute(select(Vacancy).filter_by(status='active'))  # type: ignore
            vacancies = result.scalars().all()

            if vacancies:
                # Формируем текст для отправки
                vacancies_text = "📋 *Доступные вакансии:*\n\n"
                for index, vacancy in enumerate(vacancies):
                    vacancies_text += f"{vacancy.text.strip()}\n"  # Убираем лишние пробелы и табуляции
                    if index < len(vacancies) - 1:
                        vacancies_text += '-'*30 + '\n\n'

                # Отправляем список вакансий пользователю через callback_query.message или просто через callback_query.answer()
                await callback_query.answer(vacancies_text, parse_mode="Markdown")
            else:
                # Если вакансий нет
                await callback_query.answer("На данный момент вакансий нет.")
        except SQLAlchemyError as e:
            logging.error(f"Ошибка при получении списка вакансий: {str(e)}")

