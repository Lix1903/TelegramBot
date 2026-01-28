from .db import SearchHistory
from datetime import datetime

def add_search(user_id, dep, dest, depart_date, return_date=""):
    """
    Сохраняет запрос в историю
    :param user_id: ID пользователя
    :param dep: город вылета
    :param dest: город прилёта
    :param depart_date: полная дата вылета (ГГГГ-ММ-ДД)
    :param return_date: полная дата возврата (ГГГГ-ММ-ДД)
    """
    try:
        SearchHistory.create(
            user_id=user_id,
            departure=dep,
            destination=dest,
            date=f"{depart_date} → {return_date}" if return_date else depart_date
        )
    except Exception as e:
        print(f"❌ Ошибка сохранения в БД: {e}")

def get_history(user_id, limit=5):
    return SearchHistory.select().where(SearchHistory.user_id == user_id).order_by(SearchHistory.timestamp.desc()).limit(limit)

def clear_history(user_id):
    count = SearchHistory.select().where(SearchHistory.user_id == user_id).count()
    SearchHistory.delete().where(SearchHistory.user_id == user_id).execute()
    return count