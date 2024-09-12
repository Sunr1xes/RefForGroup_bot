from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from config import GROUP_CHAT_ID
from utils import menu_handler

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
        await menu_handler(callback_query.message, "🎉 Спасибо, что вступили в группу!\nТеперь вы можете продолжить использование бота. 🚀") # type: ignore
        # await callback_query.message.edit_text( # type: ignore
        #     "🎉 Спасибо, что вступили в группу!\nТеперь вы можете продолжить использование бота. 🚀"
        # )  # type: ignore

    else:
        # Если пользователь не состоит в группе
        await callback_query.answer(
            "❗️ Вы ещё не вступили в группу.\n"
            "Пожалуйста, вступите в группу и попробуйте снова.",
            show_alert=True
        )
