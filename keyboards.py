from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from locals import LOCALS

AVAILABLE_LANGUAGES = {
    "en": "English 🇬🇧",
    "ru": "Русский 🇷🇺",
    "es": "Español 🇪🇸",
    "pt": "Português 🇵🇹",
    "fr": "Français 🇫🇷"
}


def generate_language_keyboard(selected_lang=None, stage="native", user_lang="en"):
    """
    Создаёт клавиатуру для выбора родного или изучаемого языка.
    - selected_lang: код выбранного языка (если есть)
    - stage: "native" (родной язык) или "learning" (изучаемый язык)
    - user_lang: язык интерфейса пользователя (по умолчанию "en")
    """
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Добавляем кнопки с языками
    for code, name in AVAILABLE_LANGUAGES.items():
        if selected_lang == code:
            name += " ✅"  # Добавляем галочку к выбранному языку
        keyboard.add(InlineKeyboardButton(name, callback_data=f"{stage}_{code}"))

    # Локализованные кнопки "Пропустить" и "Далее"
    skip_text = LOCALS[user_lang]["button_skip"]
    next_text = LOCALS[user_lang]["button_next"]

    if selected_lang:
        keyboard.add(InlineKeyboardButton(next_text, callback_data=f"{stage}_confirm"))
    else:
        keyboard.add(InlineKeyboardButton(skip_text, callback_data=f"{stage}_skip"))

    return keyboard


def main_menu_keyboard(user_lang="en"):
    """Создаёт главное меню с широкими кнопками."""
    keyboard = InlineKeyboardMarkup(row_width=1)  # ✅ 1 кнопка в ряду для ширины

    texts = LOCALS[user_lang]  # Берём текст кнопок на нужном языке

    keyboard.add(InlineKeyboardButton(texts["menu_dict"], callback_data="dict"))
    keyboard.add(InlineKeyboardButton(texts["menu_subscription"], callback_data="subscription"))
    keyboard.add(InlineKeyboardButton(texts["menu_invite"], callback_data="invite"))
    keyboard.add(InlineKeyboardButton(texts["menu_support"], callback_data="support"))

    return keyboard


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
    """Создаёт клавиатуру выбора количества уведомлений"""
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton(LOCALS[user_lang]["notify_3"], callback_data="notify_3"),
        InlineKeyboardButton(LOCALS[user_lang]["notify_6"], callback_data="notify_6"),
        InlineKeyboardButton(LOCALS[user_lang]["notify_12"], callback_data="notify_12")
    )