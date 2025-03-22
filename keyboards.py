from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from locals import LOCALS

AVAILABLE_LANGUAGES = {
    "en": "English 🇬🇧",
    "ru": "Русский 🇷🇺",
    "es": "Español 🇪🇸",
    "pt": "Português 🇵🇹",
    "fr": "Français 🇫🇷"
}

def generate_language_keyboard(selected_lang=None, stage="native", user_lang="en"):
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(
            name + (" ✅" if code == selected_lang else ""),
            callback_data=f"{stage}_{code}"
        )
        for code, name in AVAILABLE_LANGUAGES.items()
    ]
    keyboard.add(*buttons)

    # Добавляем кнопки "Пропустить" и "Далее"
    keyboard.add(InlineKeyboardButton(LOCALS[user_lang]["button_skip"], callback_data=f"{stage}_skip"))
    if selected_lang:
        keyboard.add(InlineKeyboardButton(LOCALS[user_lang]["button_next"], callback_data=f"{stage}_confirm"))

    return keyboard

def main_menu_keyboard(user_lang="en"):
    """Создаёт главное меню с кнопками для пользователя."""
    return ReplyKeyboardMarkup(resize_keyboard=True).add(
        KeyboardButton(LOCALS[user_lang]["menu_dict"]),
        KeyboardButton(LOCALS[user_lang]["menu_subscription"]),
        KeyboardButton(LOCALS[user_lang]["menu_invite"]),
        KeyboardButton(LOCALS[user_lang]["menu_support"])
    )

def generate_words_keyboard(selected_words, page=0, ui_lang="en", learning_lang="en"):
    """Создаёт клавиатуру выбора слов (по 8 слов, с кнопками 'Далее' и 'Завершить')."""
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Берём слова на языке изучения
    words = LOCALS[learning_lang]["word_set"][min(page, len(LOCALS[learning_lang]["word_set"]) - 1)]

    for word in words:
        is_selected = "✅ " if word in selected_words else ""
        keyboard.add(InlineKeyboardButton(is_selected + word, callback_data=f"word_{word}_{page}"))

    # 🔥 Кнопки управления страницами
    if page < 4:  # На первых 4 страницах есть "Далее"
        keyboard.add(InlineKeyboardButton(LOCALS[ui_lang]["button_next"], callback_data=f"next_page_{page + 1}"))

    # ✅ Кнопка "Завершить" (должна передавать "words_confirm")
    keyboard.add(InlineKeyboardButton("✅ " + LOCALS[ui_lang]["button_finish"], callback_data="words_confirm"))

    return keyboard


def generate_notifications_keyboard(user_lang="en"):
    """Создаёт клавиатуру выбора количества уведомлений."""
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton(LOCALS[user_lang]["notify_3"], callback_data="notify_3"),
        InlineKeyboardButton(LOCALS[user_lang]["notify_6"], callback_data="notify_6"),
        InlineKeyboardButton(LOCALS[user_lang]["notify_12"], callback_data="notify_12")
    )

def get_reply_keyboard(user_id: int):
    """Создает кнопку 'Ответить' для администратора"""
    keyboard = InlineKeyboardMarkup()
    button = InlineKeyboardButton("✉ Ответить", callback_data=f"reply_{user_id}")
    keyboard.add(button)
    return keyboard