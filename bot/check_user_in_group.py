from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from config import GROUP_CHAT_ID
from utils import menu_handler
from database import get_async_session, User
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
import logging
from handlers.registration import start_command

router = Router()

@router.callback_query(F.data == "check_user_in_group")
async def process_check_membership(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает проверку, состоит ли пользователь в группу.
    """
    bot = callback_query.bot
    user_id = callback_query.from_user.id  # type: ignore

    # Проверяем, состоит ли пользователь в группе
    member = await bot.get_chat_member(GROUP_CHAT_ID, user_id)  # type: ignore

    if member.status in ['member', 'administrator', 'creator']:
        # Если пользователь состоит в группе
        await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id) # type: ignore

        async with get_async_session() as session:
            try:
                result = await session.execute(select(User).filter(User.user_id == user_id))
                user = result.scalar_one_or_none()

                if user:
                    await menu_handler(callback_query.message, "🎉 Спасибо, что вступили в группу!\nТеперь вы можете продолжить использование бота. 🚀") # type: ignore

                else:
                    await callback_query.message.answer( # type: ignore
                        "🎉 Спасибо, что вступили в группу!\nТеперь вы можете продолжить использование бота. 🚀"
                    )  # type: ignore

                    await start_command(callback_query.message, state)

            except SQLAlchemyError as e:
                logging.error(e)
    

    else:
        # Если пользователь не состоит в группе
        await callback_query.answer(
            "❗️ Вы ещё не вступили в группу.\n"
            "Пожалуйста, вступите в группу и попробуйте снова.",
            show_alert=True
        )
