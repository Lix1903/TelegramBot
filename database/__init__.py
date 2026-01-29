from .db import init_db as init_main_db
from .models import ApiFlightResponse


def init_db():
    """Инициализирует все таблицы через Peewee"""
    init_main_db()  # Создаёт таблицу search_history
    db = ApiFlightResponse._meta.database
    db.connect()
    db.create_tables([ApiFlightResponse], safe=True)
    db.close()
    print("✅ Все таблицы инициализированы: search_history, api_flight_responses")