import logging
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from config import GROUP_CHAT_ID

async def check_membership(bot: Bot, message: Message) -> bool:
    """
    Проверяет, находится ли пользователь в чате.
    Если нет, отправляет сообщение с просьбой присоединиться к чату.
    
    :param bot: Инстанс бота
    :param message: Сообщение пользователя
    :return: True, если пользователь в чате, False если нет
    """
    user_id = message.from_user.id  # type: ignore
    try:
        member = await bot.get_chat_member(GROUP_CHAT_ID, user_id)  # type: ignore
        if member.status in ['member', 'administrator', 'creator']:
            return True
        else:
            link_on_group = InlineKeyboardButton(text="🔗 Вступить в чат", url="https://t.me/+PKddIYAM4so5MzNi")
            check_user_in_group = InlineKeyboardButton(text="🔄 Проверить", callback_data="check_user_in_group")
            inline_kb = InlineKeyboardMarkup(inline_keyboard=[[link_on_group], [check_user_in_group]])
            
            await message.answer(
                "⚠ Для использования бота вам необходимо вступить в [чат](https://t.me/+PKddIYAM4so5MzNi).\n\n"
                "После вступления нажмите 'Проверить'.",
                parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=inline_kb
            )
            return False
    except Exception as e:
        logging.error(f"Error checking user status in chat: {e}")
        await message.answer("❌ Произошла ошибка при проверке вашего статуса в чате. Пожалуйста, попробуйте позже.")
        return False
