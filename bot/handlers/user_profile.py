import logging
import pytz
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import StateFilter
from sqlalchemy.future import select
from sqlalchemy import insert, desc
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.exc import SQLAlchemyError
from database import User, get_async_session, WithdrawalHistory, ReceiptHistory
from utils import save_previous_state, get_bank_and_phone
from config import STATUS_MAP, BANK_MAP

router = Router()

class NavigationForProfile(StatesGroup):
    profile = State()
    money_withdrawal = State()
    history = State()
    history_of_withdrawal = State()
    history_of_receipts = State()
    instant_withdrawal = State()
    slow_withdrawal = State()
    instant_withdrawal_window = State()
    slow_withdrawal_window = State()
    bank_selection = State()
    card_or_phone_number_for_instant = State()
    card_or_phone_number_for_slow = State()
    
back_button = InlineKeyboardButton(text="👤 Вернуться в профиль", callback_data="back_in_profile")
back_button_1 = InlineKeyboardButton(text="⬅️ Назад", callback_data="back_in_profile")
back_button_2 = InlineKeyboardButton(text="💼 К выбору истории", callback_data="back_in_profile")
back_button_instant = InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_instant_withdrawal")
back_button_slow = InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_slow_withdrawal")

@router.message(F.text == "👤 Профиль")
async def profile_handler(message: Message, state: FSMContext):

    await save_previous_state(state)
    user_id = message.from_user.id  # type: ignore

    async with get_async_session() as db:
        try:
            result = await db.execute(select(User).filter(User.user_id == user_id))
            db_user = result.scalar_one_or_none()

            if db_user:
                # Кнопки с историями выводов и запросом вывода
                history_of_withdrawal = InlineKeyboardButton(text="📊 История", callback_data="history")
                money_withdrawal = InlineKeyboardButton(text="💸 Вывод средств", callback_data="money_withdrawal")
                inline_kb = InlineKeyboardMarkup(inline_keyboard=[[history_of_withdrawal, money_withdrawal]])

                # Формирование красивого профиля
                profile_info = (
                    f"👤 *Ваш профиль*\n\n"
                    f"📛 *Имя:* {db_user.first_name_tg}\n"
                    f"🆔 *ID:* `{db_user.user_id}`\n"
                    f"📆 *Дата регистрации:* {db_user.created_at.astimezone(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M')}\n"
                    f"💼 *Общий заработок:* {db_user.referral_earnings + db_user.work_earnings}₽\n"
                    f"💰 *Баланс на аккаунте:* {db_user.account_balance}₽\n\n"
                    f"🔻 Выберите действие ниже:"
                )

                # Обновляем состояние и отправляем сообщение с профилем
                await state.update_data(last_message=profile_info)
                await message.answer(profile_info, parse_mode="Markdown", reply_markup=inline_kb)
                await state.set_state(NavigationForProfile.profile)
            else:
                await message.answer("🚫 Ошибка. Ваш профиль не найден. Пожалуйста, перезапустите бота с помощью /start.")
        except SQLAlchemyError as e:
            logging.error("Ошибка получения пользователя из базы данных: %s", e)


@router.callback_query(F.data == "history")
async def history(callback_query: CallbackQuery, state: FSMContext):
    bot = callback_query.bot

    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore

    withdrawal_history_button = InlineKeyboardButton(text="💼 История выводов", callback_data="history_of_withdrawal")
    receipt_history_button = InlineKeyboardButton(text="💰 История поступлений", callback_data="history_of_receipts")
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[withdrawal_history_button, receipt_history_button], [back_button]])

    await callback_query.message.answer("📊 Выберите тип истории:", reply_markup=inline_kb)  # type: ignore
    await state.set_state(NavigationForProfile.history)


@router.callback_query(F.data == "history_of_receipts" | F.data.startswith("history_page_receipt_"))
async def history_of_receipts(callback_query: CallbackQuery, state: FSMContext):
    bot = callback_query.bot
    page = 1
    if callback_query.data.startswith("history_page_receipt_"): # type: ignore
        page = int(callback_query.data.split("_")[3])  # type: ignore # Получаем номер страницы из callback_data

    items_per_page = 3  # Количество транзакций на странице

    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore

    async with get_async_session() as db:
        try:
            result = await db.execute(select(User).filter(User.user_id == callback_query.from_user.id))
            db_user = result.scalar_one_or_none()

            if db_user:
                receipts = await db.execute(select(ReceiptHistory)
                                                   .filter(ReceiptHistory.user_id == db_user.user_id)
                                                   .order_by(desc(ReceiptHistory.date)))
                
                receipts = receipts.scalars().all()

                total_receipt = len(receipts)
                start = (page - 1) * items_per_page
                end = start + items_per_page
                receipts_page = receipts[start:end]

                # Формируем красивый текст с поступлениями
                text = "💰 *История поступлений:*\n\n"
                receipts_info = "\n\n──────────\n\n".join(
                    [f"🔹 *ID:* {receipt.id}\n"
                    f"💸 *Сумма:* {receipt.amount}₽\n"
                    f"📅 *Дата:* {receipt.date.astimezone(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M')}\n"
                    f"📋 *Описание:* {receipt.description or 'Нет'}\n"
                    for receipt in receipts_page]) or "🔹 История поступлений пуста."
                
                buttons = []

                if page > 1:
                    buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"history_page_receipt_{page - 1}"))
                
                if end < total_receipt:
                    buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"history_page_receipt_{page + 1}"))


                inline_kb = InlineKeyboardMarkup(inline_keyboard=[buttons, [back_button_2]])

                # Отправляем сообщение с информацией о поступлениях
                await callback_query.message.answer(text + receipts_info, reply_markup=inline_kb, parse_mode="Markdown")  # type: ignore
                await state.set_state(NavigationForProfile.history_of_receipts)
            else:
                await callback_query.message.answer("🚫 Ошибка. Ваш профиль не найден. Пожалуйста, перезапустите бота с помощью /start.") # type: ignore
        except SQLAlchemyError as e:
            logging.error("Ошибка получения пользователя из базы данных: %s", e)

@router.callback_query(F.data.startswith("history_of_withdrawal") | F.data.startswith("history_page_withdrawal_"))
async def history_of_withdrawal(callback_query: CallbackQuery, state: FSMContext):
    bot = callback_query.bot
    page = 1

    if callback_query.data.startswith("history_page_withdrawal_"): # type: ignore
        page = int(callback_query.data.split("_")[3])  # type: ignore # Получаем номер страницы из callback_data

    items_per_page = 3  # Количество транзакций на странице

    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore

    async with get_async_session() as db:
        try:
            result = await db.execute(select(User).filter(User.user_id == callback_query.from_user.id))
            db_user = result.scalar_one_or_none()

            if db_user:
                withdrawals = await db.execute(select(WithdrawalHistory)
                                               .filter(WithdrawalHistory.user_id == db_user.user_id)
                                               .order_by(desc(WithdrawalHistory.withdrawal_date)))
                
                withdrawals = withdrawals.scalars().all()
                total_withdrawals = len(withdrawals)
                start = (page - 1) * items_per_page
                end = start + items_per_page
                withdrawals_page = withdrawals[start:end]

                # Формируем красивый текст с выводом и смайликами
                text = "💸 *История выводов:*\n\n"
                withdrawals_info = "\n\n──────────\n\n".join(
                    [f"🔹 *ID:* {withdrawal.id}\n"
                    f"💰 *Сумма:* {withdrawal.amount}₽\n"
                    f"📅 *Дата:* {withdrawal.withdrawal_date.astimezone(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M')}\n"
                    f"📋 *Статус:* {STATUS_MAP.get(withdrawal.status, 'Неизвестен')}\n"
                    f"⏳ *Приоритет:* {'Быстрый' if withdrawal.is_urgent else 'Обычный'}\n"
                    f"{await get_bank_and_phone(db, withdrawal.id) or 'Нет'}\n"
                    for withdrawal in withdrawals_page]) or "🔹 История выводов пуста."

                # Клавиатура для переключения страниц
                buttons = []

                # Кнопка "Назад", если это не первая страница
                if page > 1:
                    buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"history_page_withdrawal_{page - 1}"))

                # Кнопка "Вперед", если есть больше транзакций на следующей странице
                if end < total_withdrawals:
                    buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"history_page_withdrawal_{page + 1}"))
                # Клавиатура с кнопками
                inline_kb = InlineKeyboardMarkup(inline_keyboard=[buttons, [back_button_2]])

                await callback_query.message.answer(text + withdrawals_info, parse_mode="Markdown", reply_markup=inline_kb)  # type: ignore

                await state.set_state(NavigationForProfile.history_of_withdrawal)
            else:
                await callback_query.message.answer("🚫 Ошибка. Ваш профиль не найден. Перезапустите бота с помощью /start")  # type: ignore
        except SQLAlchemyError as e:
            logging.error("Ошибка получения пользователя из базы данных: ", e)


@router.callback_query(F.data == "money_withdrawal")
async def money_withdrawal(callback_query: CallbackQuery, state: FSMContext):
    await save_previous_state(state)
    bot = callback_query.bot
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore
    
    bank_sber = InlineKeyboardButton(text="Сбербанк", callback_data="bank_sber")
    bank_tinkoff = InlineKeyboardButton(text="Тинькофф", callback_data="bank_tinkoff")
    bank_alfa = InlineKeyboardButton(text="Альфа-банк", callback_data="bank_alfa")
    bank_vtb = InlineKeyboardButton(text="ВТБ", callback_data="bank_vtb")
    bank_gasprom = InlineKeyboardButton(text="Газпромбанк", callback_data="bank_gasprom")
    bank_riff = InlineKeyboardButton(text="Райффайзенбанк", callback_data="bank_riff")

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[bank_sber, bank_tinkoff], [bank_alfa, bank_vtb], [bank_gasprom, bank_riff], [back_button]])

    await callback_query.message.answer("🏦 Выберите банк:", reply_markup=inline_kb, parse_mode="Markdown") # type: ignore
    await state.set_state(NavigationForProfile.bank_selection)


@router.callback_query(F.data.startswith("bank_"))
async def bank_selection(callback_query: CallbackQuery, state: FSMContext):
    selected_bank = callback_query.data.split("_")[1] # type: ignore
    await state.update_data(selected_bank=selected_bank)
    bot = callback_query.bot
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)  # type: ignore

    instant_withdrawal = InlineKeyboardButton(text="🏎 Моментальный вывод", callback_data="instant_withdrawal")
    slow_withdrawal = InlineKeyboardButton(text="🕓 Вывод в течении 48 часов", callback_data="slow_withdrawal")
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[instant_withdrawal, slow_withdrawal], [back_button_1]])
    await callback_query.message.answer("💸Выберите способ получения средств:", reply_markup=inline_kb, parse_mode="Markdown") # type: ignore
    await state.set_state(NavigationForProfile.money_withdrawal)


@router.callback_query(F.data == "instant_withdrawal")
async def card_or_phone_number_for_instant(callback_query: CallbackQuery, state: FSMContext):
    bot = callback_query.bot
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id) # type: ignore

    async with get_async_session() as session:
        try:
            result = await session.execute(select(User).filter(User.user_id == callback_query.from_user.id))
            db_user = result.scalar_one_or_none()

            if db_user:
                phone_number_button = InlineKeyboardButton(text=f"{db_user.phone_number}", callback_data="use_stored_phone_number")
                
            await callback_query.message.answer( # type: ignore
                "Нажмите на кнопку ниже, чтобы ввести указанный ранее номер телефона.\n"
                "ИЛИ\n"
                "Напишите вручную номер телефона или номер карты для вывода средств\n\n"
                "❗️*Проверьте правильность ввода*❗️",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[phone_number_button],[back_button_1]]),
                parse_mode="Markdown"
            )

            await state.set_state(NavigationForProfile.card_or_phone_number_for_instant)
        except SQLAlchemyError as e:
            logging.error(f"Ошибка при получении данных пользователя: {e}")
            await callback_query.message.answer("Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.") # type: ignore


@router.callback_query(F.data == "use_stored_phone_number")
async def use_stored_phone_number(callback_query: CallbackQuery, state: FSMContext):
    async with get_async_session() as session:
        try:
            result = await session.execute(select(User).filter(User.user_id == callback_query.from_user.id))
            db_user = result.scalar_one_or_none()

            if db_user:
                # Сохраняем номер телефона в состояние FSM
                await state.update_data(card_or_phone_number_for_instant=db_user.phone_number)
                
                # Переходим к следующему шагу — ввод суммы для моментального вывода
                await callback_query.message.answer( # type: ignore
                    "❗️Моментальный вывод средств❗️\n"
                    "При моментальном выводе средств присутствует комиссия 5% от суммы вывода.💸\n\n"
                    "Укажите сумму вывода\nМинимальная сумма - 100₽",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_button_1]]),
                    parse_mode="Markdown"
                )
                await state.set_state(NavigationForProfile.instant_withdrawal)
        except SQLAlchemyError as e:
            logging.error(f"Ошибка при получении данных пользователя: {e}")
            await callback_query.message.answer("Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.") # type: ignore


@router.message(NavigationForProfile.card_or_phone_number_for_instant)
async def enter_card_or_phone_number_for_instant(message: Message, state: FSMContext):
    card_or_phone_number = message.text
    await state.update_data(card_or_phone_number=card_or_phone_number)

    await message.answer("❗️Моментальный вывод средств❗️\n" # type: ignore
                                        "При моментальном выводе средств присутствует комиссия 5% от суммы вывода.💸\n\n"
                                        "Укажите сумму вывода\nМинимальная сумма - 100₽",
                                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_button_instant]]), 
                                        parse_mode="Markdown") # type: ignore
    await state.set_state(NavigationForProfile.instant_withdrawal)


@router.message(NavigationForProfile.instant_withdrawal)
async def enter_instant_withdrawal(message: Message, state: FSMContext):
    try:
        amount = float(message.text)  # type: ignore
        data = await state.get_data()
        selected_bank = data.get("selected_bank")
        card_or_phone = data.get("card_or_phone_number_for_instant")

        if amount < 100:
            await message.answer("Минимальная сумма для вывода - 100₽")
            return
        
        async with get_async_session() as db:
            try:
                # Проверка существования пользователя
                result = await db.execute(select(User).filter(User.user_id == message.from_user.id))  # type: ignore
                db_user = result.scalar_one_or_none()

                if db_user:  # Если пользователь существует
                    if db_user.account_balance >= amount:  # Проверяем, достаточно ли средств
                        db_user.account_balance -= amount
                        await db.commit()

                        # Вставляем запись в withdrawal_history только если пользователь существует
                        await db.execute(insert(WithdrawalHistory).values(
                            user_id=db_user.user_id,
                            amount=amount,
                            withdrawal_date=datetime.now(),
                            status='pending',
                            is_urgent=True, # Признак моментального вывода
                            description=f"Банк: {selected_bank}, Реквизиты: {card_or_phone}"  # Добавляем банк и реквизиты
                        ))  # Добавляем статус вывода средств
                        await db.commit()

                        inline_keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(text="👤 Вернуться в профиль", callback_data="back_in_profile")]]
                        )

                        await message.answer(f"*Заявка на вывод средств принята*\n"
                                             f"*Банк:* {BANK_MAP.get(selected_bank)}\n" # type: ignore
                                             f"*Реквизиты:* {card_or_phone}\n"
                                             f"*Сумма:* {amount}₽\n"
                                             f"*Ожидание до 10 минут*\n\n"
                                             f"*Ваш баланс:* {db_user.account_balance}₽", reply_markup=inline_keyboard, parse_mode="Markdown")
                        await state.set_state(NavigationForProfile.instant_withdrawal_window)
                    else:
                        inline_keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(text="👤 Вернуться в профиль", callback_data="back_in_profile")]]
                        )
                        await message.answer("Недостаточно средств для вывода.", reply_markup=inline_keyboard)
                        await state.set_state(NavigationForProfile.instant_withdrawal_window)
                else:  # Если пользователь не найден
                    await message.answer("Пользователь не найден. Пожалуйста, нажмите /start для регистрации.")
                    await state.clear()

            except SQLAlchemyError as e:
                logging.error("Ошибка получения пользователя из базы данных: %s", str(e))
                await message.answer("Произошла ошибка при обработке запроса. Попробуйте позже.")
                await state.clear()

    except ValueError:
        await message.answer("Пожалуйста, введите корректную сумму для вывода.")


@router.callback_query(F.data == "slow_withdrawal")
async def card_or_phone_number_for_slow(callback_query: CallbackQuery, state: FSMContext):
    bot = callback_query.bot
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id) # type: ignore

    async with get_async_session() as session:
        try:
            result = await session.execute(select(User).filter(User.user_id == callback_query.from_user.id))
            db_user = result.scalar_one_or_none()

            if db_user:
                phone_number_button = InlineKeyboardButton(text=f"{db_user.phone_number}", callback_data="use_stored_phone_number")
                
            await callback_query.message.answer( # type: ignore
                "Нажмите на кнопку ниже, чтобы ввести указанный ранее номер телефона.\n"
                "ИЛИ\n"
                "Напишите вручную номер телефона или номер карты для вывода средств\n\n"
                "❗️*Проверьте правильность ввода*❗️",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[phone_number_button],[back_button_1]]),
                parse_mode="Markdown"
            )

            await state.set_state(NavigationForProfile.card_or_phone_number_for_slow)
        except SQLAlchemyError as e:
            logging.error(f"Ошибка при получении данных пользователя: {e}")
            await callback_query.message.answer("Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.") # type: ignore

@router.message(NavigationForProfile.card_or_phone_number_for_slow)
async def enter_card_or_phone_number_for_slow(message: Message, state: FSMContext):
    card_or_phone_number_for_slow = message.text
    await state.update_data(card_or_phone_number_for_slow=card_or_phone_number_for_slow)

    await message.answer("*Вывод средств*\n\n"
                         "Вывод средств без комиссии.\n"
                         "Минимальная сумма для вывода - 100₽",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_button_slow]]),
                         parse_mode="Markdown")

    await state.set_state(NavigationForProfile.slow_withdrawal)

@router.message(NavigationForProfile.slow_withdrawal)
async def enter_slow_withdrawal(message: Message, state: FSMContext):
    try:
        amount = float(message.text)  # type: ignore
        data = await state.get_data()
        selected_bank = data.get("selected_bank")
        card_or_phone = data.get("card_or_phone_number_for_slow")

        if amount < 100:
            await message.answer("Минимальная сумма для вывода - 100₽")
            return
        async with get_async_session() as db:
            try:
                    # Проверка существования пользователя
                result = await db.execute(select(User).filter(User.user_id == message.from_user.id))  # type: ignore
                db_user = result.scalar_one_or_none()

                if db_user:  # Если пользователь существует
                    if db_user.account_balance >= amount:  # Проверяем, достаточно ли средств
                        db_user.account_balance -= amount
                        await db.commit()

                            # Вставляем запись в withdrawal_history только если пользователь существует
                        await db.execute(insert(WithdrawalHistory).values(
                            user_id=db_user.user_id,
                            amount=amount,
                            withdrawal_date=datetime.now(),
                            status='pending',
                            description=f"Банк: {selected_bank}, Реквизиты: {card_or_phone}"
                        ))  # Добавляем статус вывода средств
                        await db.commit()

                        inline_keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(text="👤 Вернуться в профиль", callback_data="back_in_profile")]]
                        )

                        await message.answer(f"*Заявка на вывод средств принята*\n"
                                            f"*Банк:* {BANK_MAP.get(selected_bank)}\n" # type: ignore
                                            f"*Реквизиты:* {card_or_phone}\n"
                                            f"*Сумма:* {amount}₽\n"
                                            f"*Ожидание до 48 часов*\n\n"
                                            f"Ваш баланс: {db_user.account_balance}₽", reply_markup=inline_keyboard, parse_mode="Markdown")
                        await state.set_state(NavigationForProfile.slow_withdrawal_window)
                    else:
                        inline_keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(text="👤 Вернуться в профиль", callback_data="back_in_profile")]]
                        )
                        await message.answer("Недостаточно средств для вывода.", reply_markup=inline_keyboard)
                        await state.set_state(NavigationForProfile.slow_withdrawal_window)
                else:  # Если пользователь не найден
                    await message.answer("Пользователь не найден. Пожалуйста, нажмите /start для регистрации.")
                    await state.clear()

            except SQLAlchemyError as e:
                logging.error("Ошибка получения пользователя из базы данных: %s", str(e))
                await message.answer("Произошла ошибка при обработке запроса. Попробуйте позже.")
                await state.clear()

    except ValueError:
        await message.answer("Пожалуйста, введите корректную сумму для вывода.")


@router.callback_query(F.data == "back_to_instant_withdrawal")
async def back_to_instant_withdrawal(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer(  # type: ignore
        "💸Выберите способ получения средств:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏎 Моментальный вывод", callback_data="instant_withdrawal"),
                 InlineKeyboardButton(text="🕓 Вывод в течении 48 часов", callback_data="slow_withdrawal"),],
                [back_button_1]
            ]
        ),
        parse_mode="Markdown"
    )
    await state.set_state(NavigationForProfile.money_withdrawal)


@router.callback_query(F.data == "back_to_slow_withdrawal")
async def back_to_slow_withdrawal(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer( # отправляем новое сообщение # type: ignore
        "💸Выберите способ получения средств:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏎 Моментальный вывод", callback_data="instant_withdrawal"),
                 InlineKeyboardButton(text="🕓 Вывод в течении 48 часов", callback_data="slow_withdrawal")],
                [back_button_1]
            ]
        ),
        parse_mode="Markdown"
    )
    await state.set_state(NavigationForProfile.money_withdrawal)


@router.callback_query(F.data == "back_in_profile", StateFilter("*"))
async def back_in_profile(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_message = data.get("last_message")  # Извлекаем сохраненное сообщение

    if not last_message:
        last_message = "Профиль не найден. Пожалуйста, перезапустите бота."  # Страховка на случай отсутствия данных

    current_state = await state.get_state()

    if current_state == NavigationForProfile.history_of_withdrawal.state or current_state == NavigationForProfile.history_of_receipts.state:
        await callback_query.message.edit_text( # type: ignore
            text="📊 Выберите тип истории:",  # Используем сохраненное сообщение
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💼 История выводов", callback_data="history_of_withdrawal"),
                     InlineKeyboardButton(text="💰 История поступлений", callback_data="history_of_receipts")],
                    [back_button]
                ]
            ),
            parse_mode="Markdown"
        )
        await state.set_state(NavigationForProfile.history)

    elif current_state == NavigationForProfile.history.state or current_state == NavigationForProfile.bank_selection.state or NavigationForProfile.slow_withdrawal or NavigationForProfile.instant_withdrawal:
        await callback_query.message.edit_text( # type: ignore
            text=last_message,  # Используем сохраненное сообщение
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📊 История", callback_data="history"),
                     InlineKeyboardButton(text="💸 Вывод средств", callback_data="money_withdrawal")]
                ]
            ),
            parse_mode="Markdown"
        )
        await state.set_state(NavigationForProfile.profile)

    elif current_state == NavigationForProfile.card_or_phone_number_for_instant.state or current_state == NavigationForProfile.card_or_phone_number_for_slow.state:
        await callback_query.message.edit_text( # type: ignore
            text="💸Выберите способ получения средств:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🏎 Моментальный вывод", callback_data="instant_withdrawal"),
                     InlineKeyboardButton(text="🕓 Вывод в течении 48 часов", callback_data="slow_withdrawal")],
                    [back_button_1]
                ]
            ),
            parse_mode="Markdown"
        )
        await state.set_state(NavigationForProfile.money_withdrawal)

    elif current_state == NavigationForProfile.money_withdrawal.state:
        await callback_query.message.edit_text( # type: ignore 
            text="🏦 Выберите банк:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Сбербанк", callback_data="bank_sber"),
                     InlineKeyboardButton(text="Тинькофф", callback_data="bank_tinkoff")],
                    [InlineKeyboardButton(text="Альфа-банк", callback_data="bank_alfa"),
                     InlineKeyboardButton(text="ВТБ", callback_data="bank_vtb")],
                    [InlineKeyboardButton(text="Газпромбанк", callback_data="bank_gasprom"),
                     InlineKeyboardButton(text="Райффайзенбанк", callback_data="bank_riff")],
                    [back_button]
                ]
            ), 
            parse_mode="Markdown"
        )
        await state.set_state(NavigationForProfile.bank_selection)


    else: 
        await callback_query.message.answer("Что-то пошло не так. Пожалуйста, попробуйте позже.") # type: ignore
        await state.clear()