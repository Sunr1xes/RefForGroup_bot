import logging
import os
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, FSInputFile
from aiogram.filters import Command

router = Router()


@router.message(Command("help"), F.text == "🆘 Помощь")
async def help_handler(message: Message):
    """
    Обрабатывает команду /help или нажатие кнопки "🆘 Помощь".
    Отправляет список доступных команд и клавишу для загрузки пользовательского соглашения.
    """
    
    # Красиво оформленный текст с подсказками и командами
    help_text = (
        "👋 *Добро пожаловать в нашего бота!*\n\n"
        "Ниже вы найдете список доступных команд и функций:\n\n"
        "🔹 */start* — начать взаимодействие с ботом\n"
        "🔹 *Профиль👤* — посмотреть информацию о вашем профиле\n"
        "🔹 *Рефералы🫂* — управление вашими рефералами\n"
        "🔹 *Актуальные вакансии👷🏻‍♂️* — список доступных вакансий\n\n"
        "❓ Если у вас есть вопросы, обратитесь в нашу поддержку: *@refbot_admin*"
    )

    # Кнопка для вывода пользовательского соглашения
    user_agreement = InlineKeyboardButton(text="📄 Пользовательское соглашение и правила", callback_data="user_agreement")
    user_agreement_inline_kb = InlineKeyboardMarkup(inline_keyboard=[[user_agreement]])
    
    # Отправка сообщения с помощью и кнопкой для пользовательского соглашения
    await message.answer(help_text, reply_markup=user_agreement_inline_kb, parse_mode="Markdown")


@router.callback_query(F.data == "user_agreement")
async def user_agreement_callback_handler(callback_query: CallbackQuery):
    """
    Отправляет пользователю документ с пользовательским соглашением при нажатии на кнопку.
    """
    # Путь к файлу на локальной файловой системе
    file_path = r"bot/user_agreement.pdf"  # Замените на реальный путь к вашему файлу
    
    if not os.path.exists(file_path):
        await callback_query.message.answer("Файл с пользовательским соглашением временно недоступен.") # type: ignore
        logging.error(f"Файл {file_path} не найден.")
        return
    
    # Создание объекта InputFile
    document = FSInputFile(file_path, filename="Пользовательское соглашение.pdf")
    
    # Отправка файла пользователю
    await callback_query.message.answer_document(document) # type: ignore
    await callback_query.answer()