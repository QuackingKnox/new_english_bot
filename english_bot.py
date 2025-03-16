from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import re
from aiogram import Bot, Dispatcher, types
from aiogram.utils.exceptions import MessageNotModified
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import executor
import asyncio
import logging
import random


API_TOKEN = '6292986477:AAGCyxZ_lBDspnuA0wJN7cJcrQeVoHe_ORs'
#API_TOKEN = '6931698246:AAEezI8VFw5VHeOA9h5UCDvXYVfM0tex6FU'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_question_order = {}
user_sessions = {}

moscow_timezone = 'Europe/Moscow'
scheduler = AsyncIOScheduler()


all_level_words = beginner_words + moderate_words + advanced_words

all_words_to_check = [word[0] for word in all_level_words]


async def create_tables():
    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()

        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                translation TEXT NOT NULL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                rating INTEGER NOT NULL
            )
        ''')

        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_messages (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                nickname TEXT NOT NULL,
                messages_per_day INTEGER NOT NULL
            )
        ''')

        await db.commit()


@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id

    await create_user_if_not_exists(user_id)

    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()

        await cursor.execute('''
            SELECT COUNT(*)
            FROM user_messages
            WHERE user_id = ?
        ''', (user_id,))
        result = await cursor.fetchone()

        if result[0] == 0:
            await cursor.execute('''
                INSERT INTO user_messages (user_id, messages_per_day, nickname)
                VALUES (?, ?, ?)
            ''', (user_id, 0, ''))
        else:
            await cursor.execute('''
                UPDATE user_messages
                SET messages_per_day = ?, nickname = ?
                WHERE user_id = ?
            ''', (0, '', user_id))

        await db.commit()

        markup = InlineKeyboardMarkup(row_width=3)
        markup.add(
            InlineKeyboardButton("3 в день", callback_data="set_messages_3"),
            InlineKeyboardButton("6 в день", callback_data="set_messages_6"),
            InlineKeyboardButton("12 в день", callback_data="set_messages_12")
        )

        sent_message = await message.answer("Привет! Я - бот, задача которого помочь тебе запомнить английские слова. Просто отправь мне слова, которые ты хочешь выучить, указав их перевод через дефис. В ответ я буду присылать тебе эти слова с вариантами ответов в течение дня. Это поможет существенно расширить твой словарный запас. А теперь скажи, сколько сообщений в день ты бы хотел(а) получать?",
                                            reply_markup=markup)

        user_question_order[user_id] = {'last_message_id': sent_message.message_id, 'message_id': message.message_id}


@dp.message_handler(commands=['stat'])
async def show_statistics_command(message: types.Message):
    await show_statistics(message)


@dp.message_handler(commands=['download'])
async def download_command(message: types.Message):
    if message.from_user.id == 302977694:
        db_path = 'eng_database.db'

        await message.answer_document(document=open(db_path, 'rb'))


async def show_statistics(message: types.Message):
    if message.from_user.id == 302977694:
        async with aiosqlite.connect('eng_database.db') as db:
            cursor = await db.cursor()

            await cursor.execute('''
                SELECT COUNT(DISTINCT user_id) AS unique_users, GROUP_CONCAT(user_id) AS user_ids, GROUP_CONCAT(nickname) AS nicknames
                FROM user_messages
            ''')
            result = await cursor.fetchone()

            unique_users = result[0]
            user_ids = result[1]
            nicknames = result[2]

            user_info = [f"{nickname} ({user_id})" if nickname else str(user_id) for user_id, nickname in
                         zip(user_ids.split(','), nicknames.split(','))]

            await message.answer(
                f"Уникальные пользователи: {unique_users}\nИнформация о пользователях: {', '.join(user_info)}")
    else:
        await message.answer("У вас нет разрешения использовать эту команду.")


@dp.message_handler(commands=['delete'])
async def send_delete_buttons(message: types.Message):
    user_id = message.from_user.id

    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()

        # Fetch active words for the user
        await cursor.execute("SELECT id, word FROM words WHERE user_id = ? AND status = 'active'", (user_id,))
        words = await cursor.fetchall()

        if not words:
            await message.answer("Не найдено слов для удаления.")
            return

        user_sessions[user_id] = {"current_page": 1, "words_per_page": 10}

        await show_delete_buttons(user_id)


@dp.message_handler(lambda message: True)
async def echo_all(message: types.Message):
    user_id = message.from_user.id
    await create_user_if_not_exists(user_id)

    if message.text == "/ask":
        await send_quiz(user_id)
    else:
        matches = re.findall(r'(.+?) - (.+)', message.text)

        if not matches:
            await message.answer("""Пожалуйста, следуйте шаблону: 
house - дом
water - вода""")

        else:
            for word, translation in matches:
                word = word.strip().lower()
                translation = translation.strip().lower()

                await add_word(user_id, word, translation)
                await message.answer(f"Добавлено: {word} - {translation}")


@dp.callback_query_handler(lambda c: c.data.startswith('set_messages'))
async def process_set_messages_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    messages_per_day = int(callback_query.data.split("_")[-1])
    nickname = callback_query.from_user.username

    user_identifier = nickname if nickname else str(user_id)

    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()

        # Check if the user exists in the user_messages table
        await cursor.execute('''
            SELECT COUNT(*)
            FROM user_messages
            WHERE user_id = ?
        ''', (user_id,))
        result = await cursor.fetchone()

        if result[0] == 0:
            # If the user doesn't exist, insert a new record
            await cursor.execute('''
                INSERT INTO user_messages (user_id, messages_per_day, nickname)
                VALUES (?, ?, ?)
            ''', (user_id, messages_per_day, user_identifier))
        else:
            # If the user exists, update the existing record
            await cursor.execute('''
                UPDATE user_messages
                SET messages_per_day = ?, nickname = ?
                WHERE user_id = ?
            ''', (messages_per_day, user_identifier, user_id))

        await db.commit()

    await bot.delete_message(user_id, user_question_order[user_id]['last_message_id'])

    await bot.send_message(user_id, f"Количество сообщений в день установлено: {messages_per_day}")

    await reset_scheduler_tasks()

    await send_level_selection_message(user_id)


async def send_level_selection_message(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Новичок", callback_data="set_level_beginner"),
        InlineKeyboardButton("Средний", callback_data="set_level_intermediate"),
        InlineKeyboardButton("Продвинутый", callback_data="set_level_advanced"),
        InlineKeyboardButton("Без набора", callback_data="set_level_independent"),
    )

    message_text = (
        'Теперь вы можете выбрать набор стандартных слов, который подходит для вашего уровня '
        'знаний английского языка, либо добавлять слова самостоятельно, выбрав "без набора":'
    )

    await bot.send_message(user_id, message_text, reply_markup=markup)


@dp.callback_query_handler(lambda c: c.data.startswith('set_level'))
async def process_set_level_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    proficiency_level = callback_query.data.split("_")[-1]

    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()

        words_placeholders = ','.join(['?'] * len(all_words_to_check))

        await cursor.execute(f"DELETE FROM words WHERE user_id = ? AND word IN ({words_placeholders})",
                             (user_id, *all_words_to_check))
        await db.commit()

    words_to_add = []

    if proficiency_level == "beginner":
        words_to_add = beginner_words
    elif proficiency_level == "intermediate":
        words_to_add = moderate_words
    elif proficiency_level == "advanced":
        words_to_add = advanced_words
    elif proficiency_level == "independent":
        pass

    for word, translation in words_to_add:
        await add_word(user_id, word, translation)

    await bot.delete_message(user_id, callback_query.message.message_id)

    await bot.send_message(user_id, f"Вы выбрали: {proficiency_level}")


async def get_active_words_for_user(user_id):
    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()

        # Получить список активных слов для данного пользователя
        await cursor.execute("SELECT word, translation FROM words WHERE user_id = ? AND status = 'active'", (user_id,))
        existing_words = await cursor.fetchall()

    return existing_words


@dp.callback_query_handler(lambda c: c.data.startswith('confirm_delete'))
async def process_confirm_delete_callback(callback_query: types.CallbackQuery):
    word_id = int(callback_query.data.split("_")[2])

    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()

        # Fetch the word to be confirmed for deletion
        await cursor.execute("SELECT word FROM words WHERE id = ?", (word_id,))
        result = await cursor.fetchone()

        if result:
            word = result[0]

            # Send a confirmation message with "Yes" and "No" buttons
            confirmation_markup = InlineKeyboardMarkup().add(
                InlineKeyboardButton("Да", callback_data=f"delete_{word_id}"),
                InlineKeyboardButton("Нет", callback_data="cancel_delete")
            )
            await bot.edit_message_text(
                chat_id=callback_query.from_user.id,
                message_id=callback_query.message.message_id,
                text=f"Вы точно хотите удалить слово '{word}'?",
                reply_markup=confirmation_markup
            )
        else:
            await bot.send_message(callback_query.from_user.id, "Ошибка: слово не найдено.")


@dp.callback_query_handler(lambda c: c.data.startswith('delete'))
async def process_delete_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    word_id = int(callback_query.data.split("_")[1])

    try:
        # Fetch the word to be deleted
        async with aiosqlite.connect('eng_database.db') as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT word FROM words WHERE id = ?", (word_id,))
            result = await cursor.fetchone()

            if result:
                deleted_word = result[0]

                # Update the status in the database
                await cursor.execute("UPDATE words SET status = 'delete' WHERE id = ?", (word_id,))
                await db.commit()

                await bot.answer_callback_query(callback_query.id, text=f"Вы удалили слово {deleted_word}.")
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=callback_query.message.message_id,
                    text=f"Вы удалили слово {deleted_word}."
                )

                # Покажем кнопки для удаления следующих слов
                await show_delete_buttons(user_id)
            else:
                # Обработка случая, когда fetchone() вернуло None
                await bot.answer_callback_query(callback_query.id, text="Ошибка: слово не найдено.")
    except Exception as e:
        # Обработка других исключений, если они возникнут
        await bot.answer_callback_query(callback_query.id, text=f"Произошла ошибка: {str(e)}")


async def show_delete_buttons(user_id):
    current_page = user_sessions[user_id]["current_page"]
    words_per_page = user_sessions[user_id]["words_per_page"]

    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()

        # Fetch active words for the user
        await cursor.execute("SELECT id, word FROM words WHERE user_id = ? AND status = 'active'", (user_id,))
        words = await cursor.fetchall()

        total_pages = (len(words) - 1) // words_per_page + 1

        if current_page < 1:
            current_page = 1
        elif current_page > total_pages:
            current_page = total_pages

        start_index = (current_page - 1) * words_per_page
        end_index = start_index + words_per_page
        current_words = words[start_index:end_index]

        markup = InlineKeyboardMarkup(row_width=2)
        for word_id, word in current_words:
            callback_data = f"confirm_delete_{word_id}"
            markup.add(InlineKeyboardButton(word, callback_data=callback_data))

        arrow_buttons = InlineKeyboardMarkup(row_width=2)
        if current_page == 1 and total_pages > 1:
            arrow_buttons.add(InlineKeyboardButton(">", callback_data="next_page"))
        elif 1 < current_page < total_pages:
            arrow_buttons.add(InlineKeyboardButton("<", callback_data="prev_page"),
                              InlineKeyboardButton(">", callback_data="next_page"))
        elif current_page == total_pages and total_pages > 1:
            arrow_buttons.add(InlineKeyboardButton("<", callback_data="prev_page"))

        if arrow_buttons.inline_keyboard:
            markup.add(*arrow_buttons.inline_keyboard[0])

        last_message_id = user_sessions[user_id].get("last_message_id")
        if last_message_id:
            try:
                await bot.edit_message_reply_markup(chat_id=user_id, message_id=last_message_id, reply_markup=None)
            except MessageNotModified:
                pass

        try:
            if last_message_id:
                message = await bot.edit_message_text(chat_id=user_id, message_id=last_message_id,
                                                      text=f"Выберите слово для удаления (страница {current_page}/{total_pages}):",
                                                      reply_markup=markup)
            else:
                message = await bot.send_message(user_id, f"Выберите слово для удаления (страница {current_page}/{total_pages}):",
                                                 reply_markup=markup)

            user_sessions[user_id]["last_message_id"] = message.message_id
        except MessageNotModified:
            pass


@dp.callback_query_handler(lambda c: c.data == 'prev_page')
async def process_prev_page_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_sessions[user_id]["current_page"] -= 1
    await show_delete_buttons(user_id)


@dp.callback_query_handler(lambda c: c.data == 'next_page')
async def process_next_page_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_sessions[user_id]["current_page"] += 1
    await show_delete_buttons(user_id)


@dp.callback_query_handler(lambda c: c.data == 'cancel_delete')
async def process_cancel_delete_callback(callback_query: types.CallbackQuery):
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        message_id=callback_query.message.message_id,
        text="Удаление отменено."
    )


async def add_word(user_id, word, translation):
    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()

        # Ensure user entry exists in the 'words' table
        await cursor.execute("INSERT OR IGNORE INTO words (id) VALUES (?)", (user_id,))

        # Insert new word with status 'active' and initial rating of 0
        await cursor.execute("INSERT INTO words (user_id, word, translation, status, rating) VALUES (?, ?, ?, 'active', 0)",
                             (user_id, word, translation))

        await db.commit()


def validate_input(text: str) -> bool:
    pattern = r'^.+ - .+$'
    return bool(re.match(pattern, text))


async def create_user_if_not_exists(user_id):
    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()

        await cursor.execute("INSERT OR IGNORE INTO words (id) VALUES (?)", (user_id,))
        await db.commit()


async def send_quiz(user_id):
    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()

        # Fetch random active words with the lowest ratings for the user
        await cursor.execute("SELECT word, translation FROM (SELECT word, translation FROM words WHERE status = 'active' AND user_id = ? ORDER BY rating LIMIT 10) ORDER BY RANDOM() LIMIT 4;", (user_id,))
        words = await cursor.fetchall()

        if not words:
            return

        correct_word = random.choice(words)

        correct_word_text, correct_translation = correct_word
        options = [word for word, _ in words]

        user_question_order[user_id] = {
            'correct_word': correct_word,
            'options': options
        }

        markup = InlineKeyboardMarkup(row_width=2)
        for idx, option in enumerate(options):
            callback_data = f"answer_{idx}"
            markup.add(InlineKeyboardButton(option, callback_data=callback_data))

        await bot.send_message(chat_id=user_id, text=f"Как переводится слово {correct_translation}?", reply_markup=markup)


@dp.callback_query_handler(lambda c: c.data.startswith('answer'))
async def process_callback(callback_query: types.CallbackQuery):
    chosen_index = int(callback_query.data.split("_")[1])

    user_id = callback_query.from_user.id
    user_data = user_question_order.get(user_id)

    if not user_data or user_data.get('answer_fixed'):
        return

    if 'chosen_indices' in user_data:
        chosen_indices = user_data['chosen_indices']
    else:
        chosen_indices = []

    user_data['answer_fixed'] = True
    chosen_indices.append(chosen_index)
    user_data['chosen_indices'] = chosen_indices

    if not user_data:
        return

    if 'keyboard_count' not in user_data:
        user_data['keyboard_count'] = 1
    else:
        user_data['keyboard_count'] += 1

    correct_word, correct_translation = user_data['correct_word']
    options = user_data['options']

    markup = InlineKeyboardMarkup()

    for i, option in enumerate(options):
        button_text = f"{option}"
        if i in chosen_indices:
            if option == correct_word:
                button_text += " ✅"
            else:
                button_text += " ❌"

        callback_data = f"answer_{i}"
        markup.add(InlineKeyboardButton(button_text, callback_data=callback_data))

    original_question = f"Как переводится слово {correct_translation}?"

    await bot.edit_message_text(chat_id=user_id, message_id=callback_query.message.message_id,
                                text=original_question, reply_markup=markup)

    if options[chosen_index] == correct_word:
        await bot.answer_callback_query(callback_query.id, text="Правильно!")

        keyboard_count = user_data.get('keyboard_count', 0)

        # Подключаемся к базе данных, чтобы узнать количество всех слов пользователя
        async with aiosqlite.connect('eng_database.db') as db:
            cursor = await db.cursor()

            # Получаем количество всех слов пользователя
            await cursor.execute('''
                SELECT COUNT(*)
                FROM words
                WHERE user_id = ? AND status = 'active'
            ''', (user_id,))
            result = await cursor.fetchone()
            total_words_count = result[0] if result else 0

        # Определяем, сколько очков добавить в зависимости от попытки
        if keyboard_count == 1:
            rating_increment = total_words_count
        elif keyboard_count == 2:
            rating_increment = total_words_count // 2
        else:
            rating_increment = 0

        # Обновляем рейтинг слова
        async with aiosqlite.connect('eng_database.db') as db:
            cursor = await db.cursor()

            await cursor.execute('''
                SELECT rating FROM words
                WHERE user_id = ? AND word = ? AND translation = ?
            ''', (user_id, correct_word, correct_translation))
            result = await cursor.fetchone()

            if result:
                current_rating = result[0]
                new_rating = current_rating + rating_increment

                await cursor.execute('''
                    UPDATE words
                    SET rating = ?
                    WHERE user_id = ? AND word = ? AND translation = ?
                ''', (new_rating, user_id, correct_word, correct_translation))

                await db.commit()
    else:
        await bot.answer_callback_query(callback_query.id, text="Неверно! Попробуйте снова.")
        user_data['answer_fixed'] = False


async def update_ratings():
    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()
        await cursor.execute('''
            UPDATE words
            SET rating = rating - 1
             ''')
        await db.commit()


async def scheduler_jobs(dp):
    async with aiosqlite.connect('eng_database.db') as db:
        cursor = await db.cursor()

        await cursor.execute("SELECT user_id, messages_per_day FROM user_messages")
        user_data = await cursor.fetchall()

        for user_id, messages_per_day in user_data:
            if messages_per_day == 12:
                cron_trigger_send_quiz = CronTrigger.from_crontab('0 8-20 * * *', timezone=moscow_timezone)
                scheduler.add_job(send_quiz, trigger=cron_trigger_send_quiz, args=[user_id])
            elif messages_per_day == 6:
                cron_trigger_send_quiz = CronTrigger.from_crontab('0 8-20/2 * * *', timezone=moscow_timezone)
                scheduler.add_job(send_quiz, trigger=cron_trigger_send_quiz, args=[user_id])
            elif messages_per_day == 3:
                cron_trigger_send_quiz = CronTrigger.from_crontab('0 8-20/4 * * *', timezone=moscow_timezone)
                scheduler.add_job(send_quiz, trigger=cron_trigger_send_quiz, args=[user_id])

        cron_trigger_update_ratings = CronTrigger.from_crontab('0 0 * * *', timezone=moscow_timezone)
        scheduler.add_job(update_ratings, trigger=cron_trigger_update_ratings)

        scheduler.start()


async def reset_scheduler_tasks():
    if scheduler.running:
        scheduler.shutdown(wait=False)

    jobs = scheduler.get_jobs()
    for job in jobs:
        job.remove()

    await scheduler_jobs(dp)


async def on_startup(dp):
    await create_tables()
    await scheduler_jobs(dp)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(executor.start_polling(dp, on_startup=on_startup, skip_updates=True))
