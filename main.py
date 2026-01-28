import logging
import os
from loader import bot
from database import init_db
from utils.api import init_db as init_api_db  # Добавлено: инициализация таблицы API
import handlers  # noqa

log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    try:
        init_db()          # Инициализация основной БД (история поиска)
        init_api_db()      # Инициализация таблицы api_flight_responses
        logger.info("✅ База данных инициализирована")
        logger.info("🚀 Бот запущен")
        bot.polling(none_stop=True)
    except Exception as e:
        logger.critical(f"❌ Бот упал: {e}", exc_info=True)

if __name__ == '__main__':
    main()