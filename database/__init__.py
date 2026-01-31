from .db import init_db as init_main_db
from .models import ApiFlightResponse


def init_db():
    """Инициализирует все таблицы через Peewee"""
    init_main_db()  # Создаёт таблицу search_history
    # Получаем базу данных из модели Peewee
    database = ApiFlightResponse._meta.database  # type: ignore[attr-defined]
    database.connect()
    database.create_tables([ApiFlightResponse], safe=True)
    database.close()
    print("✅ Все таблицы инициализированы: search_history, api_flight_responses")