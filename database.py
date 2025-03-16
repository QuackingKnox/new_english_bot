import aiosqlite
import datetime
from config import DB_PATH


DEFAULT_TIMEZONES = {
    "en": 0,  # UTC
    "ru": 3,  # Москва UTC+3
    "es": -5,  # Испания UTC-5
    "pt": -3,  # Бразилия UTC-3
    "fr": 1   # Франция UTC+1
}


async def create_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        # Создание таблицы users
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT DEFAULT NULL,
            ui_lang TEXT DEFAULT 'en',
            learning_lang TEXT DEFAULT 'en',
            timezone INTEGER DEFAULT 0 CHECK(timezone BETWEEN -12 AND 12),
            preferences TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Создание таблицы words
        await db.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            translation TEXT NOT NULL,
            status TEXT CHECK(status IN ('Active', 'Learned', 'Deleted')) DEFAULT 'Active',
            type TEXT CHECK(type IN ('noun', 'adjective', 'verb', 'adverb', 'pronoun', 'other')),
            learning_lang TEXT NOT NULL,
            translation_lang TEXT NOT NULL,
            learned_counter INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """)

        # Создание таблицы limits
        await db.execute("""
        CREATE TABLE IF NOT EXISTS limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            friend_limits INTEGER DEFAULT 0,
            bought_limits INTEGER DEFAULT 0,
            free_limits INTEGER DEFAULT 50,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """)

        await db.commit()


async def get_user(user_id):
    """Возвращает данные пользователя, включая язык интерфейса и изучаемый язык."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, ui_lang, learning_lang, timezone, preferences FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            user = await cursor.fetchone()
            return user  # Вернёт (user_id, ui_lang, learning_lang, timezone, preferences) или None



async def add_user(user_id, username=None):
    """Добавляет нового пользователя в БД."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, username, ui_lang, timezone, preferences) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, "en", DEFAULT_TIMEZONES["en"], None)
        )
        await db.commit()


async def update_user_language(user_id, language, native=True):
    """Обновляет родной или изучаемый язык пользователя и выставляет timezone."""
    column = "ui_lang" if native else "learning_lang"
    timezone = DEFAULT_TIMEZONES.get(language, 0)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {column} = ?, timezone = ? WHERE user_id = ?", (language, timezone, user_id))
        await db.commit()


async def update_preferences(user_id, preferences):
    """Обновляет предпочтения пользователя (количество уведомлений)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET preferences = ? WHERE user_id = ?", (preferences, user_id))
        await db.commit()


async def save_selected_words_to_db(user_id, selected_words, learning_lang, translation_lang):
    """Сохраняет выбранные пользователем слова в БД с информацией о языке перевода."""
    async with aiosqlite.connect(DB_PATH) as db:
        for word in selected_words:
            print(f'🔥 Запись слова "{word}" в БД (учим: {learning_lang}, переводим на: {translation_lang})')  # Отладка

            await db.execute(
                "INSERT INTO words (user_id, word, translation, status, type, learning_lang, translation_lang) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, word, "", "Active", "other", learning_lang, translation_lang)
            )

        await db.commit()



async def get_user_stats(user_id):
    """Возвращает полную статистику пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Выученные слова
        async with db.execute(
            "SELECT COUNT(*) FROM words WHERE user_id = ? AND status = 'Learned'", (user_id,)
        ) as cursor:
            learned_words = (await cursor.fetchone())[0]

        # Всего добавленных слов
        async with db.execute(
            "SELECT COUNT(*) FROM words WHERE user_id = ?", (user_id,)
        ) as cursor:
            total_words = (await cursor.fetchone())[0]

        # Активные слова (те, что в процессе изучения)
        async with db.execute(
            "SELECT COUNT(*) FROM words WHERE user_id = ? AND status = 'Active'", (user_id,)
        ) as cursor:
            active_words = (await cursor.fetchone())[0]

        # Дата первого слова
        async with db.execute(
            "SELECT MIN(created_at) FROM words WHERE user_id = ?", (user_id,)
        ) as cursor:
            first_word_date = await cursor.fetchone()
            first_word_date = first_word_date[0] if first_word_date else None

    # Вычисляем, сколько дней пользователь обучается
    if first_word_date:
        first_day = datetime.datetime.strptime(first_word_date, "%Y-%m-%d %H:%M:%S")
        days_learning = (datetime.datetime.utcnow() - first_day).days
    else:
        days_learning = 0

    # Вычисляем прогресс (процент изученных слов)
    progress = round((learned_words / total_words * 100), 1) if total_words > 0 else 0

    return learned_words, total_words, active_words, days_learning, progress

