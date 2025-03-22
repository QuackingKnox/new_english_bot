from aiogram import types
from aiogram.dispatcher import Dispatcher
from aiogram.types import CallbackQuery
from locals import LOCALS
from database import (
    get_user,
    add_user,
    update_user_language,
    update_preferences,
    save_selected_words_to_db,
    get_user_stats
)
from keyboards import (
    generate_language_keyboard,
    generate_words_keyboard,
    generate_notifications_keyboard,
    main_menu_keyboard,
)
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram import types
from config import ADMIN_ID


selected_words_dict = {}  # Запоминаем слова пользователя (user_id -> set)


async def send_welcome(message: types.Message):
    """Показывает пользователю статистику и главное меню."""
    user_id = message.from_user.id
    username = message.from_user.username

    user = await get_user(user_id)

    if user is None:
        # Если пользователя нет в БД, предлагаем выбрать родной язык
        await add_user(user_id, username)
        await message.answer(
            LOCALS["en"]["start_welcome"],
            reply_markup=generate_language_keyboard(stage="native", user_lang="en")
        )
    else:
        lang = user[1] if user[1] else "en"  # Получаем язык интерфейса

        # Получаем полную статистику пользователя
        learned_words, total_words, active_words, days_learning, progress = await get_user_stats(user_id)

        # Формируем сообщение со статистикой
        stats_message = LOCALS[lang]["stats_message"].format(
            learned=learned_words,
            total=total_words,
            active=active_words,
            days=days_learning,
            progress=progress
        )

        await message.answer(
            stats_message,
            reply_markup=main_menu_keyboard(lang)
        )


async def set_native_language(call: CallbackQuery):
    """Сохраняет родной язык пользователя и предлагает выбрать изучаемый."""
    user_id = call.from_user.id
    selected_option = call.data.split("_")[1]  # Например, "native_ru"

    if selected_option == "skip":
        native_lang = "en"  # Если пользователь пропустил выбор, ставим английский
    elif selected_option == "confirm":
        # Если нажата кнопка "Далее", переходим к следующему шагу
        user = await get_user(user_id)
        native_lang = user[1] if user else "en"
        await call.message.edit_text(
            LOCALS[native_lang]["start_choose_learning"],
            reply_markup=generate_language_keyboard(stage="learning", user_lang=native_lang)
        )
        return
    else:
        native_lang = selected_option

    # Обновляем язык пользователя
    await update_user_language(user_id, native_lang)
    await call.message.edit_text(
        LOCALS[native_lang]["start_welcome"],  # Тот же текст, но теперь кнопка "Далее"
        reply_markup=generate_language_keyboard(selected_lang=native_lang, stage="native", user_lang=native_lang)
    )


async def set_learning_language(call: CallbackQuery):
    """Сохраняет изучаемый язык, но НЕ меняет язык интерфейса."""
    user_id = call.from_user.id
    selected_option = call.data.split("_")[1]  # Например, "learning_es"

    # Получаем родной язык пользователя (UI язык) и изучаемый язык
    user = await get_user(user_id)

    if not user:
        return

    ui_lang = user[1]  # UI язык (интерфейс)
    learning_lang = user[2] if user[2] else "en"  # Язык, который учит пользователь

    if selected_option == "confirm":
        # Переходим к шагу выбора слов
        await call.message.edit_text(
            LOCALS[ui_lang]["choose_words"],
            reply_markup=generate_words_keyboard(set(), ui_lang=ui_lang, learning_lang=learning_lang)
        )
        return

    if selected_option == "skip":
        learning_lang = user[1] if user else "en"  # По умолчанию изучаем родной язык
    else:
        learning_lang = selected_option

    # Записываем изучаемый язык в БД (но UI язык НЕ меняем!)
    await update_user_language(user_id, learning_lang, native=False)

    await call.message.edit_text(
        LOCALS[ui_lang]["start_choose_learning"],  # UI остаётся на родном языке
        reply_markup=generate_language_keyboard(selected_lang=learning_lang, stage="learning", user_lang=ui_lang)
    )


async def select_word(call: CallbackQuery):
    """Добавляет/удаляет слово, оставаясь на текущей странице и не меняя язык."""
    user_id = call.from_user.id
    data_parts = call.data.split("_")
    word = "_".join(data_parts[1:-1])  # Восстанавливаем слово, если оно из нескольких частей
    page = int(data_parts[-1])  # Получаем текущую страницу

    user = await get_user(user_id)
    if not user:
        return

    ui_lang = user["ui_lang"]
    learning_lang = user["learning_lang"]

    # ✅ Безопасное добавление словаря пользователя
    selected_words = selected_words_dict.setdefault(user_id, set())

    # Добавляем или удаляем слово
    if word in selected_words:
        selected_words.remove(word)
    else:
        selected_words.add(word)

    await call.message.edit_reply_markup(
        reply_markup=generate_words_keyboard(selected_words, page, ui_lang=ui_lang, learning_lang=learning_lang)
    )



async def next_page(call: CallbackQuery):
    """Переключение страниц слов, сохраняя выбор пользователя и правильный язык обучения."""
    page = int(call.data.split("_")[2])
    user_id = call.from_user.id
    user = await get_user(user_id)

    if not user:
        return

    ui_lang = user["ui_lang"]
    learning_lang = user["learning_lang"]

    # ✅ Безопасное добавление словаря пользователя
    selected_words = selected_words_dict.setdefault(user_id, set())

    await call.message.edit_text(
        LOCALS[ui_lang]["choose_words"],
        reply_markup=generate_words_keyboard(selected_words, page, ui_lang=ui_lang, learning_lang=learning_lang)
    )



async def confirm_words(call: CallbackQuery):
    """Сохраняем слова пользователя в БД и предлагаем завершить выбор."""
    user_id = call.from_user.id
    user = await get_user(user_id)

    if not user:
        return

    ui_lang = user["ui_lang"]
    learning_lang = user["learning_lang"]

    # ✅ Безопасное получение словаря пользователя
    selected_words = selected_words_dict.get(user_id, set())

    if not selected_words:
        await call.answer(LOCALS[ui_lang]["no_words_selected"], show_alert=True)
        return

    # ✅ Сохраняем слова в БД
    await save_selected_words_to_db(user_id, selected_words, learning_lang, ui_lang)

    await call.message.edit_text(
        LOCALS[ui_lang]["confirm_words_message"],
        reply_markup=generate_notifications_keyboard(ui_lang)
    )

    # ✅ Чистим список выбранных слов после сохранения
    selected_words_dict.pop(user_id, None)



async def finish_word_selection(call: CallbackQuery):
    """Переход к настройке уведомлений после завершения выбора слов."""
    user_id = call.from_user.id
    user = await get_user(user_id)
    user_lang = user[1] if user else "en"

    await call.message.edit_text(
        LOCALS[user_lang]["select_words_done"],
        reply_markup=generate_notifications_keyboard(user_lang)  # Вызов готовой клавиатуры
    )


async def set_notifications(call: CallbackQuery):
    """Сохраняет частоту уведомлений."""
    user_id = call.from_user.id
    times_per_day = int(call.data.split("_")[1])

    await update_preferences(user_id, times_per_day)

    user = await get_user(user_id)
    user_lang = user[1] if user else "en"

    await call.message.edit_text(LOCALS[user_lang]["setup_complete"])

class SupportState(StatesGroup):
    waiting_for_question = State()
    waiting_for_reply = State()


async def help_info(callback: types.CallbackQuery):
    """Отображает раздел поддержки"""
    user = get_user(callback.from_user.id)
    language = user[5] if user else "ru"

    keyboard = create_inline_menu(language, section="support")
    await callback.message.edit_text(LANGUAGES[language]["support_info_message"], reply_markup=keyboard)
    await callback.answer()



async def receive_support_message(message: types.Message):
    """Получает сообщение от пользователя в разделе 'Поддержка' и отправляет его администратору"""
    user = get_user(message.from_user.id)
    language = user[5] if user else "ru"

    admin_message = (
        f"📩 Новый вопрос в поддержку!\n\n"
        f"👤 Пользователь: @{message.from_user.username} ({message.from_user.id})\n"
        f"💬 Вопрос: {message.text}"
    )

    keyboard = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("Ответить", callback_data=f"reply_{message.from_user.id}")
    )

    await bot.send_message(ADMIN_ID, admin_message, reply_markup=keyboard)
    await message.answer(LANGUAGES[language]["question_received_message"])


async def process_admin_reply(callback: types.CallbackQuery, state: FSMContext):
    """Фиксируем, кому отвечает админ"""
    user_id = int(callback.data.split("_")[1])
    await state.update_data(user_id=user_id)
    await AdminReply.waiting_for_reply.set()

    await callback.message.answer(f"✍ Введите ответ для пользователя {user_id}:")
    await callback.answer()


async def handle_admin_reply(message: types.Message, state: FSMContext):
    """Отправляет ответ от администратора пользователю с учетом его языка"""
    data = await state.get_data()
    user_id = data.get("user_id")

    if user_id:
        user = await get_user(user_id)  # Используем обновленный get_user()
        language = user["ui_lang"] if user else "ru"  # Если нет данных, ставим "ru" по умолчанию

        try:
            await bot.send_message(user_id, f"{LOCALS[language]['admin_reply_message']}\n{message.text}")
            await message.answer("✅ Ответ отправлен пользователю.")
        except Exception as e:
            await message.answer(f"⚠ Ошибка при отправке ответа: {e}")

    await state.finish()

def register_handlers(dp: Dispatcher):
    """Регистрируем обработчики команд и коллбэков."""

    def register_handlers(dp: Dispatcher):
        # Основные команды
        dp.register_message_handler(send_welcome, commands=["start"])
        dp.register_message_handler(receive_support_message, content_types=types.ContentTypes.TEXT)
        dp.register_message_handler(handle_admin_reply, state=AdminReply.waiting_for_reply,
                                    content_types=types.ContentTypes.TEXT)

        # Callback-хендлеры
        dp.register_callback_query_handler(set_native_language, lambda c: c.data.startswith("native_"))
        dp.register_callback_query_handler(set_learning_language, lambda c: c.data.startswith("learning_"))
        dp.register_callback_query_handler(select_word, lambda c: c.data.startswith("word_"))
        dp.register_callback_query_handler(next_page, lambda c: c.data.startswith("next_page_"))
        dp.register_callback_query_handler(confirm_words, lambda c: c.data == "words_confirm")
        dp.register_callback_query_handler(finish_word_selection, lambda c: c.data == "words_finish")
        dp.register_callback_query_handler(set_notifications, lambda c: c.data.startswith("notify_"))
        dp.register_callback_query_handler(process_admin_reply, lambda c: c.data.startswith("reply_"), state="*")



