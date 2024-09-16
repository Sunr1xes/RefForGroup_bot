import logging
import asyncio
import gspread
from google.oauth2.service_account import Credentials
from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from aiolimiter import AsyncLimiter
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.future import select
from sqlalchemy import delete
from utils import is_admins, send_transaction_list, save_previous_state
from config import GROUP_CHAT_ID, REFERRAL_PERCENTAGE
from database import get_async_session, User, WithdrawalHistory, BlackList, Referral, ReceiptHistory

#TODO сделать админку для вакансий

router = Router()
limiter = AsyncLimiter(30, 1)

scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
client = gspread.authorize(creds) # type: ignore

class AdminMenu(StatesGroup):
    menu = State()
    funds_transfer = State()
    change_balance = State()
    blacklist_user = State()
    unblock_user = State()
    delete_user = State()
    transaction = State()
    broadcast = State()

back_button = InlineKeyboardButton(text="Назад", callback_data="back_in_admin_menu")

@router.message(Command("admin_menu"))
async def admin_menu(message: types.Message, state: FSMContext):
    """ 
    Логика для команды /admin_menu. 
    """
    await save_previous_state(state)
    user_id = message.from_user.id  # type: ignore
    logging.info(f"Admin menu called by user: {user_id}")

    # Проверяем, является ли пользователь администратором
    if not await is_admins(user_id):
        logging.warning(f"Access denied for user: {user_id}")
        return

    # Клавиатура для админских действий
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Перевод средств", callback_data="funds_transfer")],
        [InlineKeyboardButton(text="💰 Изменить баланс", callback_data="change_balance")],
        [InlineKeyboardButton(text="🚫 Заблокировать пользователя", callback_data="blacklist_user")],
        [InlineKeyboardButton(text="✅ Разблокировать пользователя", callback_data="unblock_user")],
        [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data="delete_user")],
        [InlineKeyboardButton(text="🧾 Транзакции", callback_data="transactions")],
        [InlineKeyboardButton(text="📨 Рассылка всем пользователям", callback_data="broadcast")]
    ])

    text = "⚙️ *Панель администратора* ⚙️\nВыберите действие ниже:"
    await state.update_data(last_message=text)
    # Отправляем сообщение с админским меню
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(AdminMenu.menu)
    logging.info(f"Admin menu displayed for user: {user_id}")


@router.callback_query(F.data == "funds_transfer")
async def funds_transfer(callback_query: CallbackQuery, state: FSMContext):
    """
    По docs google переводит средства на счета отработавших пользователей и их реферрерам.
    """
    await callback_query.bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await callback_query.message.answer( # type: ignore
        "💸 *Перевод средств*\n\n"
        "Введите ссылку на docs google:",
        parse_mode="Markdown",
        reply_markup=inline_kb
    )
    await state.set_state(AdminMenu.funds_transfer)


@router.message(AdminMenu.funds_transfer)
async def funds_transfer_command(message: Message, state: FSMContext):
    logging.info(f"Received command for funds transfer: {message.text}")

    if not await is_admins(message.from_user.id):  # type: ignore
        logging.warning(f"Access denied for user {message.from_user.id}")  # type: ignore
        return
    
    doc_url = message.text

    if not doc_url.startswith("https://docs.google.com/"):  # type: ignore
        await message.answer("Некорректная ссылка. Попробуйте ещё раз.")
        return

    sheet = client.open_by_url(doc_url)  # type: ignore
    worksheet = sheet.get_worksheet(0)
    rows = worksheet.get_all_records()

    async with get_async_session() as session:
        with session.no_autoflush:  # Синхронное использование session.no_autoflush
            for row in rows:
                try:
                    user_id = int(row["ID tg"])
                    earning = float(row["зп"])

                    result = await session.execute(select(User).where(User.user_id == user_id))
                    user = result.scalar_one_or_none()

                    if user:
                        user.account_balance += earning

                        # Добавляем запись в историю поступлений
                        receipt_history = ReceiptHistory(
                            user_id=user.user_id,
                            amount=earning,
                            description="Поступление средств за отработанную смену"
                        )
                        session.add(receipt_history)

                        results = await session.execute(select(Referral).where(Referral.referral_id == user.id))
                        referral = results.scalar_one_or_none()

                        if referral:
                            result = await session.execute(select(User).where(User.id == referral.user_id))
                            referrer = result.scalar_one_or_none()
                            if referrer:
                                referrer_earning = earning * REFERRAL_PERCENTAGE
                                referrer.account_balance += referrer_earning

                                referrer_receipt_history = ReceiptHistory(
                                    user_id=referrer.user_id,
                                    amount=referrer_earning,
                                    description=f"Реферальное поступление за пользователя ID: {user.user_id}"
                                )
                                session.add(referrer_receipt_history)

                        await session.commit()
                    else:
                        logging.warning(f"User with ID {user_id} not found.")
                        await message.answer(f"Пользователь с ID {user_id} не найден.")
                except SQLAlchemyError as e:
                    await session.rollback()
                    logging.error(f"Error processing row: {row}")
                    logging.error(f"Error: {e}")
                    await message.answer("Произошла ошибка. Пожалуйста, повторите попытку позже.")
    
    await state.clear()
    await message.answer("✅ Средства перечислены.")


@router.callback_query(F.data == "change_balance")
async def change_balance(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает запрос на изменение баланса.
    Запрашивает ID пользователя и новый баланс.
    """
    await callback_query.bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore
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
    await callback_query.bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore
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
    await callback_query.bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore
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
    await callback_query.bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await callback_query.message.answer("🗑 Пожалуйста, введите ID пользователя для удаления в формате:\n`<user_id>`\n\nНе рекомендуется это действие, так как могут возникнуть проблемы с базой данных", # type: ignore
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
    logging.info(f"Received command for deleting user: {message.text}")
    if not await is_admins(message.from_user.id):  # type: ignore
        logging.warning(f"Access denied for user {message.from_user.id}")  # type: ignore
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


@router.callback_query(F.data == "broadcast")
async def process_broadcast(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку "Рассылка".
    Запрашивает у администратора сообщение для рассылки.
    """
    await callback_query.bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore
    if not await is_admins(callback_query.from_user.id):  # type: ignore
        logging.warning(f"Access denied for user: {callback_query.from_user.id}")  # type: ignore
        return
    
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await callback_query.message.answer("📨 Пожалуйста, введите сообщение для рассылки в формате:\n`<message>`", # type: ignore
                                        parse_mode="Markdown", 
                                        reply_markup=inline_kb
                                        )
    await state.set_state(AdminMenu.broadcast)


@router.message(AdminMenu.broadcast)
async def broadcast_command(message: types.Message, state: FSMContext):
    """
    Обработчик команды рассылки для админов.
    Рассылка сообщения всем пользователям в базе данных.
    """
    logging.info(f"Received command for broadcasting: {message.text}")
    if not await is_admins(message.from_user.id):  # type: ignore
        logging.warning(f"Access denied for user {message.from_user.id}")  # type: ignore
        return

    message_text = message.text
    
    await message.answer("✅ Рассылка началась. Ожидайте...")
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing") # type: ignore
    
    try:
        async with get_async_session() as db:
            result = await db.execute(select(User))
            users = result.scalars().all()

        sent_count = 0
        failed_count = 0

        async def send_message_to_users(user):
            nonlocal sent_count, failed_count
            try:
                async with limiter:
                    await message.bot.send_message(chat_id=user.user_id, text=message_text, parse_mode="Markdown") # type: ignore
                    sent_count += 1
            except Exception as e:
                logging.error(f"Failed to send message to user {user}: {e}")
                failed_count += 1

        await message.bot.delete_message(message.chat.id, message.message_id) # type: ignore
        await asyncio.gather(*(send_message_to_users(user) for user in users))
        await message.answer(f"✅ Рассылка завершена. Отправлено: {sent_count}. Ошибок: {failed_count}.")
    
    except SQLAlchemyError as e:
        await message.answer(f"❌ Произошла ошибка при отправке сообщения. Попробуйте позже.\n\n{e}")
        logging.error(f"Error committing the change: {e}")
    
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
        return
    
    current_state = await state.get_state()

    if current_state in [AdminMenu.delete_user, AdminMenu.change_balance, AdminMenu.blacklist_user, AdminMenu.unblock_user, AdminMenu.broadcast, AdminMenu.funds_transfer]:
        #await callback_query.bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id) # type: ignore
        await callback_query.message.edit_text( # type: ignore
            text=last_message,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Изменить баланс", callback_data="change_balance")],
                    [InlineKeyboardButton(text="🚫 Заблокировать пользователя", callback_data="blacklist_user")],
                    [InlineKeyboardButton(text="✅ Разблокировать пользователя", callback_data="unblock_user")],
                    [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data="delete_user")],
                    [InlineKeyboardButton(text="🧾 Транзакции", callback_data="transactions")], 
                    [InlineKeyboardButton(text="📨 Рассылка всем пользователям", callback_data="broadcast")]
                ]
            ),
            parse_mode="Markdown"
        )
        await state.set_state(AdminMenu.menu)
    else:
        await callback_query.message.answer("Что-то пошло не так. Пожалуйста, попробуйте позже.") # type: ignore
        await state.clear()
