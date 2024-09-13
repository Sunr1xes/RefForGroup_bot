import logging
from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.future import select
from sqlalchemy import delete
from utils import is_admins, send_transaction_list, save_previous_state
from config import GROUP_CHAT_ID
from database import get_async_session, User, WithdrawalHistory, BlackList, Referral

#TODO сделать админку для вакансий

router = Router()

class AdminMenu(StatesGroup):
    menu = State()
    change_balance = State()
    blacklist_user = State()
    unblock_user = State()
    delete_user = State()
    transaction = State()

back_button = InlineKeyboardButton(text="Назад", callback_data="back_in_admin_menu")

@router.message(Command("admin_menu"))
async def admin_menu(message: types.Message, state: FSMContext):
    await save_previous_state(state)
    user_id = message.from_user.id  # type: ignore
    logging.info(f"Admin menu called by user: {user_id}")

    # Проверяем, является ли пользователь администратором
    if not await is_admins(user_id):
        logging.warning(f"Access denied for user: {user_id}")
        return

    # Клавиатура для админских действий
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Изменить баланс", callback_data="change_balance")],
        [InlineKeyboardButton(text="🚫 Заблокировать пользователя", callback_data="blacklist_user")],
        [InlineKeyboardButton(text="✅ Разблокировать пользователя", callback_data="unblock_user")],
        [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data="delete_user")],
        [InlineKeyboardButton(text="🧾 Транзакции", callback_data="transactions")]
    ])

    text = "⚙️ *Панель администратора* ⚙️\nВыберите действие ниже:"
    await state.update_data(last_message=text)
    # Отправляем сообщение с админским меню
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(AdminMenu.menu)
    logging.info(f"Admin menu displayed for user: {user_id}")



@router.callback_query(F.data == "change_balance")
async def change_balance(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает запрос на изменение баланса.
    Запрашивает ID пользователя и новый баланс.
    """
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await callback_query.message.answer( # type: ignore
        "💳 *Изменение баланса*\n\n"
        "Введите ID пользователя и новый баланс в формате:\n\n"
        "`<user_id> <new_balance>`\n\n"
        "Например: `123456789 1000`",
        parse_mode="Markdown",
        reply_markup=inline_kb
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


async def is_user_blocked(user_id: int) -> bool:
    async with get_async_session() as session:
        result = await session.execute(select(BlackList).where(BlackList.user_id == user_id))
        blocked_user = result.scalar_one_or_none()
        return blocked_user is not None


@router.callback_query(F.data == "blacklist_user")
async def blacklist_user(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку "Черный список" для админов.
    Запрашивает ID пользователя для блокировки.
    """

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await callback_query.message.answer("🚫 Пожалуйста, введите ID пользователя для блокировки в формате:\n`<user_id>`", # type: ignore
                                        parse_mode="Markdown", 
                                        reply_markup=inline_kb
                                        )
    await state.set_state(AdminMenu.blacklist_user)


@router.message(AdminMenu.blacklist_user)
async def blacklist_user_command(message: Message, state: FSMContext):
    logging.info(f"Received command for blacklisting user: {message.text}")

    if not await is_admins(message.from_user.id):  # type: ignore
        logging.warning(f"Access denied for user {message.from_user.id}")  # type: ignore
        return
    
    args = message.text.split()  # type: ignore
    if len(args) != 1:
        await message.answer("❌ Некорректный формат.\nИспользуйте: `<user_id>`", parse_mode="Markdown")
        return
    
    try:
        user_id = int(args[0])
    except (IndexError, ValueError):
        await message.answer("❌ Некорректные данные. Убедитесь, что вы ввели числовое значение для ID.")
        return
    
    if await is_user_blocked(user_id):
        await message.answer("❌ Пользователь уже заблокирован.")
    else:
        async with get_async_session() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            db_user = result.scalar_one_or_none()
            if db_user:
                try:
                    new_blacklist = BlackList(
                        user_id=db_user.user_id
                    )
                    session.add(new_blacklist)
                    await session.commit()
                    try:
                        await message.bot.ban_chat_member( # type: ignore
                            chat_id=GROUP_CHAT_ID, # type: ignore
                            user_id=db_user.user_id
                        )
                        logging.info(f"User {user_id} added to blacklist and kicked from the group.")
                        await message.answer("✅ Пользователь заблокирован и исключен из чата.")
                    except TelegramBadRequest as e:
                        logging.error(f"Error kicking user {user_id} from the group: {e}")
                        await message.answer("⚠️ Не удалось исключить пользователя {user_id} из чата. Возможно, бот не имеет прав администратора.")

                except SQLAlchemyError as e:
                    await session.rollback()
                    logging.error(f"Error adding user to blacklist: {e}")
                    await message.answer("❌ Произошла ошибка при добавлении пользователя в черный список.")
                    return
            else:
                await message.answer("❌ Пользователь не найден.")

        await state.clear()
           

@router.callback_query(F.data == "unblock_user")
async def unblock_user(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку "Разблокировать" для админов.
    Запрашивает ID пользователя для разблокировки.
    """

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await callback_query.message.answer( # type: ignore
        "✅ Пожалуйста, введите ID пользователя для разблокировки в формате:\n`<user_id>`",
        parse_mode="Markdown", 
        reply_markup=inline_kb
    )
    await state.set_state(AdminMenu.unblock_user)

@router.message(AdminMenu.unblock_user)
async def unblock_user_command(message: Message, state: FSMContext):
    logging.info(f"Received command for unblocking user: {message.text}")

    if not is_admins(message.from_user.id):  # type: ignore
        return
    
    args = message.text.split()  # type: ignore
    if len(args) != 1:
        await message.answer("❌ Некорректный формат.\nИспользуйте: `<user_id>`", parse_mode="Markdown")
        return
    
    try:
        user_id = int(args[0])
    except (IndexError, ValueError):
        await message.answer("❌ Некорректные данные. Убедитесь, что вы ввели числовое значение для ID.")
        return
    
    if not await is_user_blocked(user_id):
        await message.answer("✅ Пользователь уже разблокирован.")
    else:
        async with get_async_session() as session:
            result = await session.execute(select(BlackList).where(BlackList.user_id == user_id))
            db_user = result.scalar_one_or_none()
            if db_user:
                try:
                    await session.delete(db_user)
                    await session.commit()
                    logging.info(f"Admin {message.from_user.id} User unblocked user {user_id}") # type: ignore
                    await message.answer("✅ Пользователь разблокирован.")
                    try:
                        await message.bot.unban_chat_member(chat_id=GROUP_CHAT_ID, user_id=user_id) # type: ignore
                        await message.bot.send_message(user_id, "✅ Вы были разблокированы и можете зайти в чат.\nБольше не нарушайте правила.\nДобро пожаловать!")  # type: ignore
                    except Exception as e: 
                        logging.error(f"Error sending message to user {user_id}: {e}")
                except SQLAlchemyError as e:
                    await session.rollback()
                    logging.error(f"Error unblocking user: {e}")
                    await message.answer("❌ Произошла ошибка при разблокировке пользователя.")
                    return
            else:
                await message.answer("❌ Пользователь не найден.")

        await state.clear()

@router.callback_query(F.data == "transactions")
async def list_transactions(callback_query: CallbackQuery):
    """
    Обрабатывает нажатие на кнопку "Транзакции" для админов.
    """

    user_id = callback_query.from_user.id  # type: ignore
    logging.info(f"Admin menu called by user: {user_id}")

    # Проверяем, является ли пользователь администратором
    if not await is_admins(user_id):
        logging.warning(f"Access denied for user: {user_id}")
        return

    bot = callback_query.bot

    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore
    await callback_query.message.answer("📋 *Транзакции* 📋", parse_mode="Markdown")  # type: ignore

    async with get_async_session() as db:
        try:
            # Срочные транзакции
            urgent_transactions = await db.execute(
                select(WithdrawalHistory)
                .options(joinedload(WithdrawalHistory.user))  # Загрузка связанных данных пользователя
                .filter(WithdrawalHistory.is_urgent == True, WithdrawalHistory.status == 'pending')
                .order_by(WithdrawalHistory.withdrawal_date)
            )
            urgent_transactions = urgent_transactions.scalars().all()

            # Обычные транзакции
            normal_transactions = await db.execute(
                select(WithdrawalHistory)
                .options(joinedload(WithdrawalHistory.user))  # Загрузка связанных данных пользователя
                .filter(WithdrawalHistory.is_urgent == False, WithdrawalHistory.status == 'pending')
                .order_by(WithdrawalHistory.withdrawal_date)
            )
            normal_transactions = normal_transactions.scalars().all()

        except SQLAlchemyError as e:
            logging.error(f"Error fetching transactions: {e}")
            await bot.send_message(callback_query.message.chat.id, "⚠️ Произошла ошибка при получении транзакции. Попробуйте позже.")  # type: ignore
            return
        
        # Отправляем списки транзакций
        await send_transaction_list(bot, callback_query.message.chat.id, urgent_transactions, "🔥 Срочные транзакции") # type: ignore
        await send_transaction_list(bot, callback_query.message.chat.id, normal_transactions, "💼 Обычные транзакции") # type: ignore

    await callback_query.answer()

@router.callback_query(F.data.startswith("approve_"))
async def approve_transaction(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id  # type: ignore
    bot = callback_query.bot

    # Проверяем, является ли пользователь администратором
    if not await is_admins(user_id):
        logging.warning(f"Access denied for user: {user_id}")
        return
    
    txn_id = int(callback_query.data.split("_")[1]) # type: ignore

    # Обновляем статус транзакции в базе данных
    async with get_async_session() as db:
        result = await db.execute(select(WithdrawalHistory).filter(WithdrawalHistory.id == txn_id))
        transaction = result.scalar_one_or_none()

        await callback_query.message.edit_reply_markup(reply_markup=None) # type: ignore

        if transaction and transaction.status == 'pending':
            transaction.status = 'approved'
            await db.commit()
            await callback_query.answer(f"Транзакция ID {txn_id} одобрена.", show_alert=True)
            await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore
        else:
            await callback_query.answer("Невозможно одобрить транзакцию.", show_alert=True)

@router.callback_query(F.data.startswith("cancel_"))
async def cancel_transaction(callback_query: CallbackQuery):

    user_id = callback_query.from_user.id  # type: ignore

    # Проверяем, является ли пользователь администратором
    if not await is_admins(user_id):
        logging.warning(f"Access denied for user: {user_id}")
        return
    
    txn_id = int(callback_query.data.split("_")[1]) # type: ignore

    # Обновляем статус транзакции в базе данных
    async with get_async_session() as db:
        result = await db.execute(select(WithdrawalHistory).filter(WithdrawalHistory.id == txn_id))
        transaction = result.scalar_one_or_none()

        await callback_query.message.edit_reply_markup(reply_markup=None) # type: ignore

        if transaction and transaction.status == 'pending':
            transaction.status = 'cancelled'
            await db.commit()
            await callback_query.answer(f"Транзакция ID {txn_id} отменена.", show_alert=True)
            await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore
        else:
            await callback_query.answer("Невозможно отменить транзакцию.", show_alert=True)


@router.callback_query(F.data == "delete_user")
async def process_delete_user(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку "Удалить пользователя".
    Запрашивает у администратора ID пользователя для удаления.
    """
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await callback_query.message.answer("🗑 Пожалуйста, введите ID пользователя для удаления в формате:\n`<user_id>`", # type: ignore
                                        parse_mode="Markdown", 
                                        reply_markup=inline_kb
                                        )
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
        await db.execute(delete(Referral).where(Referral.user_id == user_id))
        await db.execute(delete(Referral).where(Referral.referral_id == user_id))

        result = await db.execute(select(User).filter(User.user_id == user_id))
        db_user = result.scalar_one_or_none()

        if db_user:
            try:
                await db.delete(db_user)
                await db.commit()
                await message.answer(f"✅ Пользователь с ID `{user_id}` был успешно удален.", parse_mode="Markdown")
            except SQLAlchemyError as e:
                await db.rollback()
                await message.answer("❌ Произошла ошибка при удалении пользователя. Попробуйте позже.")
                logging.error(f"Error committing the change: {e}")
        else:
            await message.answer("❌ Пользователь с указанным ID не найден.")
    
    await state.clear()


@router.callback_query(F.data == "back_in_admin_menu", StateFilter("*"))
async def back_in_admin_menu(callback_query: CallbackQuery, state: FSMContext):
    """
    Обработчик нажатия на кнопку "Назад" в меню администратора.
    """
    data = await state.get_data()
    last_message = data.get("last_message")

    if not last_message:
        last_message = "Неизвестная ошибка"
    
    current_state = await state.get_state()

    if current_state == AdminMenu.delete_user or current_state == AdminMenu.change_balance or current_state == AdminMenu.blacklist_user or current_state == AdminMenu.unblock_user:
        await callback_query.bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id) # type: ignore
        await callback_query.message.edit_text( # type: ignore
            text=last_message,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Изменить баланс", callback_data="change_balance")],
                    [InlineKeyboardButton(text="🚫 Заблокировать пользователя", callback_data="blacklist_user")],
                    [InlineKeyboardButton(text="✅ Разблокировать пользователя", callback_data="unblock_user")],
                    [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data="delete_user")],
                    [InlineKeyboardButton(text="🧾 Транзакции", callback_data="transactions")]
                ]
            ),
            parse_mode="Markdown"
        )
        await state.set_state(AdminMenu.menu)
    else:
        await callback_query.message.answer("Что-то пошло не так. Пожалуйста, попробуйте позже.") # type: ignore
        await state.clear()
