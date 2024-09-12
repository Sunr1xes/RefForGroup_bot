import logging
import asyncio
from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from database import User, get_async_session 
from aiogram.filters import Command
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from utils import prompt_for_registration, menu_handler
from referral_system import ReferralSystem
from membership import check_membership, is_user_blocked

#TODO доделать проверку на фио при регистрации
#TODO чуть изменить начальное приветствие, сделать более красивым

router = Router()

class Registration(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_contact = State()

@router.message(Command("start"))
async def start_command(message: Message, state: FSMContext):
    """
    Логика для команды /start. Если пользователь переходит по реферальной ссылке, то передается ID реферера.
    В других случаях стандартная обработка.
    """

    if await is_user_blocked(message.from_user.id):  # type: ignore # Проверка на блокировку
        await message.answer("❌ Вы заблокированы и не можете пользоваться ботом.")
        return
    
    if not await check_membership(message.bot, message):  # type: ignore # Проверка на членство в группе
        return  # Пользователь не в группе, дальнейший код не выполняется

    user_id = message.from_user.id  # type: ignore

    # Проверка членства в группе
    async with get_async_session() as db:
        result = await db.execute(select(User).filter(User.user_id == user_id))
        db_user = result.scalar_one_or_none()

        if db_user:
            # Если пользователь уже зарегистрирован, показываем ему меню
            await menu_handler(message, "👋 Добро пожаловать обратно!")
        else:
            # Если пользователь переходит по реферальной ссылке
            if len(message.text.split()) > 1:  # type: ignore
                referrer_id = int(message.text.split()[1])  # type: ignore # Извлекаем ID реферера из ссылки
                await state.update_data(referrer_id=referrer_id)

            # Запрос ввода ФИО для нового пользователя
            await message.answer(
                "👋 Добро пожаловать!\n\n"
                "Для начала работы введите свои ФИО в формате:\n"
                "*Иван Иванович Иванов*.",
                parse_mode="Markdown"
            )
            await state.set_state(Registration.waiting_for_full_name.state)


    
@router.message(Registration.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext):
    full_name = message.text.strip()  # type: ignore # Убираем лишние пробелы в начале и конце

    # Проверка, что введено три слова и все слова состоят из букв
    if len(full_name.split()) != 3 or not all(word.isalpha() for word in full_name.split()):
        await message.answer(
            "❗ Пожалуйста, введите полное ФИО в правильном формате.\n"
            "Пример: Иван Иванович Иванов"
        )
        return

    # Сохраняем данные пользователя во временном хранилище
    await state.update_data(full_name=full_name)

    # Переходим к следующему шагу - запрос номера телефона
    await prompt_for_registration(message)
    await state.set_state(Registration.waiting_for_contact)


@router.message(Registration.waiting_for_contact, F.content_type == "contact")
async def contact_handler(message: Message, state: FSMContext):

    bot = message.bot
    user_id = message.from_user.id  # type: ignore

    # Проверка членства в группе

    contact = message.contact

    if contact is None:
        await message.answer("❗ Контактные данные не были переданы.")
        return
    
    # Получение данных из контактной информации
    user_name_tg = contact.first_name or ""
    last_user_name_tg = contact.last_name or ""
    phone_number = contact.phone_number or ""
    
    # Получение данных пользователя из временного хранилища
    user_data = await state.get_data()
    full_name = user_data.get("full_name")
    referrer_id = user_data.get("referrer_id")

    if not full_name:
        await message.answer("❗ Произошла ошибка. Попробуйте зарегистрироваться снова.")
        return

    try:
        # Разбиваем полное имя на фамилию, имя и отчество
        last_name, first_name, patronymic = full_name.split()  # type: ignore
    except ValueError:
        await message.answer("❗ Введите корректное полное имя в формате: Фамилия Имя Отчество.")
        return

    # Работа с базой данных
    async with get_async_session() as db:
        result = await db.execute(select(User).filter(User.user_id == user_id))
        db_user = result.scalar_one_or_none()

        if not db_user:
            # Создаем нового пользователя
            new_user = User(
                user_id=user_id,
                first_name_tg=user_name_tg,
                last_name_tg=last_user_name_tg,
                last_name=last_name,
                first_name=first_name,
                patronymic=patronymic,
                phone_number=phone_number
            )
            db.add(new_user)
            try:
                await db.commit()
                logging.info(f"User {last_name, first_name, patronymic} - {user_name_tg} with ID {user_id} has been added to the database.")
                # Отправляем сообщение пользователю
                if referrer_id:
                    success, msg = await ReferralSystem.process_referral(user_id, referrer_id)
                    await message.answer(msg)
                    
                await menu_handler(message, "🎉 Спасибо, регистрация прошла успешно!")

                logging.info(f"User {last_name, first_name, patronymic} - {user_name_tg} with ID {user_id} has been added to the database.")
            except SQLAlchemyError as e:
                await db.rollback()
                await message.answer("❗ Произошла ошибка при регистрации, попробуйте позже.")
                logging.error(f"Error saving user to database: {e}")
        
    await state.clear()

