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
    user_id = message.from_user.id # type: ignore
    logging.info(f"Admin menu called by user: {user_id}")

    if not await is_admins(user_id):
        logging.warning(f"Access denied for user: {user_id}")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить баланс", callback_data="change_balance")],
        [InlineKeyboardButton(text="Удалить пользователя", callback_data="delete_user")]
    ])

    await message.answer("Панель администратора:", reply_markup=keyboard)
    logging.info(f"Admin menu displayed for user: {user_id}")


@router.callback_query(F.data == "change_balance")
async def change_balance(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer("Введите ID пользователя и новый баланс в формате: <user_id> <new_balance>") # type: ignore
    await state.set_state(AdminMenu.change_balance)

@router.message(AdminMenu.change_balance)
async def change_balance_command(message: Message, state: FSMContext):
    logging.info(f"Received command for changing balance: {message.text}")

    if not await is_admins(message.from_user.id): # type: ignore
        logging.warning(f"Access denied for user {message.from_user.id}") # type: ignore
        return

    args = message.text.split() # type: ignore
    if len(args) != 2:
        await message.answer("Некорректный формат. Используйте: <user_id> <new_balance>")
        return

    try:
        user_id = int(args[0])
        new_balance = float(args[1])
    except ValueError:
        await message.answer("Некорректные данные. Пожалуйста, убедитесь, что вы ввели числовые значения.")
        return

    if new_balance.is_integer():
        new_balance = int(new_balance)

    async with get_async_session() as db:
        result = await db.execute(select(User).filter(User.user_id == user_id))
        db_user = result.scalar_one_or_none()

        if db_user:
            db_user.account_balance = new_balance
            logging.info(f"Changing balance for user {user_id} to {new_balance}")
            try:
                await db.commit()
                logging.info(f"Balance changed successfully for user {user_id}")
                await message.answer(f"Баланс пользователя {user_id} успешно изменен на {new_balance}.")
            except SQLAlchemyError as e:
                await db.rollback()
                await message.answer("Произошла ошибка при обновлении баланса.")
                logging.error(f"Error committing the change: {e}")
        else:
            await message.answer("Пользователь не найден.")
    await state.clear()



@router.callback_query(F.data == "delete_user")
async def process_delete_user(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer("Введите ID пользователя для удаления в формате: <user_id>") # type: ignore
    await state.set_state(AdminMenu.delete_user)

@router.message(AdminMenu.delete_user)
async def delete_user_command(message: types.Message, state: FSMContext):
    """
    Обработчик команды /delete_user <user_id> для админов.
    Удаляет пользователя с указанным ID из базы данных.
    """
    if not await is_admins(message.from_user.id): # type: ignore
        return

    args = message.text.split() # type: ignore
    if len(args) != 1:
        await message.answer("Некорректный формат. Используйте: <user_id>")
        return

    user_id = int(args[0])

    async with get_async_session() as db:
        result = await db.execute(select(User).filter(User.user_id == user_id))
        db_user = result.scalar_one_or_none()

        if db_user:
            await db.delete(db_user)
            try:
                await db.commit()
                await message.answer(f"Пользователь {user_id} успешно удален.")
            except SQLAlchemyError as e:
                await db.rollback()
                await message.answer("Произошла ошибка при удалении пользователя.")
                logging.error(f"Error committing the change: {e}")
        else:
            await message.answer("Пользователь не найден.")
    await state.clear()