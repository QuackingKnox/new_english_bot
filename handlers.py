from aiogram import types
from aiogram.dispatcher import Dispatcher
# from keyboards import create_inline_menu
# from database import add_user, get_user, update_language
# from languages import LANGUAGES


async def send_welcome(message: types.Message):
    """Отправляет главное меню пользователю при старте"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    add_user(user_id, username)
    user = get_user(user_id)
    language = user[5] if user else "ru"

    inline_menu = create_inline_menu(language)
    await message.answer(LANGUAGES[language]["main_menu"], reply_markup=inline_menu)


def register_handlers(dp: Dispatcher):
    dp.register_message_handler(send_welcome, commands=["start"])










