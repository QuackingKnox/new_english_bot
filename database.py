import aiosqlite
import asyncio


async def create_tables(path):
    async with aiosqlite.connect(path) as db:
        # Создание таблицы users
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT DEFAULT NULL,
            ui_lang TEXT DEFAULT 'ru',
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