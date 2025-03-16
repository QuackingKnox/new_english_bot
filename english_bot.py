import logging
from aiogram import Bot, Dispatcher, executor, types
from config import BOT_TOKEN
import handlers
import asyncio
from database import create_tables

# Настроим логирование
logging.basicConfig(level=logging.INFO)

# Создаем бота и диспетчер
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)

# Регистрируем обработчики
handlers.register_handlers(dp)

async def on_startup(dp):
    """Функция, которая запускается перед запуском бота"""
    await create_tables()
    logging.info("✅ База данных инициализирована")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)

