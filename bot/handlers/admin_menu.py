import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from utils import is_admins
from database import get_async_session, User

router = Router()

class AdminMenu(StatesGroup):
    change_balance = State()
    delete_user = State()

@router.message(Command("admin_menu"))
async def admin_menu(message: types.Message):
    user_id = message.from_user.id  # type: ignore
    logging.info(f"Admin menu called by user: {user_id}")

    # Проверяем, является ли пользователь администратором
    if not await is_admins(user_id):
        logging.warning(f"Access denied for user: {user_id}")
        return

    # Клавиатура для админских действий
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Изменить баланс", callback_data="change_balance")],
        [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data="delete_user")]
    ])

    # Отправляем сообщение с админским меню
    await message.answer("⚙️ *Панель администратора* ⚙️\nВыберите действие ниже:", reply_markup=keyboard, parse_mode="Markdown")
    logging.info(f"Admin menu displayed for user: {user_id}")



@router.callback_query(F.data == "change_balance")
async def change_balance(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает запрос на изменение баланса.
    Запрашивает ID пользователя и новый баланс.
    """
    await callback_query.message.answer( # type: ignore
        "💳 *Изменение баланса*\n\n"
        "Введите ID пользователя и новый баланс в формате:\n\n"
        "`<user_id> <new_balance>`\n\n"
        "Например: `123456789 1000`",
        parse_mode="Markdown"
    )  # type: ignore
    await state.set_state(AdminMenu.change_balance)


@router.message(AdminMenu.change_balance)
async def change_balance_command(message: Message, state: FSMContext):
    logging.info(f"Received command for changing balance: {message.text}")

    # Проверка прав администратора
    if not await is_admins(message.from_user.id):  # type: ignore
        logging.warning(f"Access denied for user {message.from_user.id}")  # type: ignore
        return

    # Парсинг введенных данных
    args = message.text.split()  # type: ignore
    if len(args) != 2:
        await message.answer("❌ Некорректный формат.\nИспользуйте: `<user_id> <new_balance>`", parse_mode="Markdown")
        return

    # Проверка на корректные числовые данные
    try:
        user_id = int(args[0])
        new_balance = float(args[1])
    except ValueError:
        await message.answer("❌ Некорректные данные. Убедитесь, что вы ввели числовые значения для ID и баланса.")
        return

    # Приведение баланса к целому числу, если это возможно
    if new_balance.is_integer():
        new_balance = int(new_balance)

    # Работа с базой данных
    async with get_async_session() as db:
        result = await db.execute(select(User).filter(User.user_id == user_id))
        db_user = result.scalar_one_or_none()

        if db_user:
            db_user.account_balance = new_balance
            logging.info(f"Changing balance for user {user_id} to {new_balance}")
            try:
                await db.commit()
                logging.info(f"Balance changed successfully for user {user_id}")
                await message.answer(f"✅ Баланс пользователя с ID `{user_id}` успешно изменен на `{new_balance}` ₽.", parse_mode="Markdown")
            except SQLAlchemyError as e:
                await db.rollback()
                await message.answer("⚠️ Произошла ошибка при обновлении баланса. Попробуйте позже.")
                logging.error(f"Error committing the change: {e}")
        else:
            await message.answer("❌ Пользователь не найден.")
    
    # Очистка состояния
    await state.clear()



@router.callback_query(F.data == "delete_user")
async def process_delete_user(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку "Удалить пользователя".
    Запрашивает у администратора ID пользователя для удаления.
    """
    await callback_query.message.answer("🗑 Пожалуйста, введите ID пользователя для удаления в формате:\n`<user_id>`", parse_mode="Markdown")  # type: ignore
    await state.set_state(AdminMenu.delete_user)


@router.message(AdminMenu.delete_user)
async def delete_user_command(message: types.Message, state: FSMContext):
    """
    Обработчик команды удаления пользователя для админов.
    Удаляет пользователя с указанным ID из базы данных.
    """
    if not await is_admins(message.from_user.id):  # type: ignore
        return

    args = message.text.split()  # type: ignore
    if len(args) != 1:
        await message.answer("❗️ Некорректный формат. Используйте: `<user_id>`", parse_mode="Markdown")
        return

    try:
        user_id = int(args[0])
    except ValueError:
        await message.answer("❗️ Введите корректный ID пользователя.")
        return

    async with get_async_session() as db:
        result = await db.execute(select(User).filter(User.user_id == user_id))
        db_user = result.scalar_one_or_none()

        if db_user:
            await db.delete(db_user)
            try:
                await db.commit()
                await message.answer(f"✅ Пользователь с ID `{user_id}` был успешно удален.", parse_mode="Markdown")
            except SQLAlchemyError as e:
                await db.rollback()
                await message.answer("❌ Произошла ошибка при удалении пользователя. Попробуйте позже.")
                logging.error(f"Error committing the change: {e}")
        else:
            await message.answer("❌ Пользователь с указанным ID не найден.")
    
    await state.clear()
