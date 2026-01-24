import os
from peewee import SqliteDatabase, Model, IntegerField, TextField, DateTimeField, DateField
from datetime import datetime

DB_PATH = os.path.join("database", "history.db")
os.makedirs("database", exist_ok=True)

db = SqliteDatabase(DB_PATH)

class SearchHistory(Model):
    user_id = IntegerField()
    departure = TextField()
    destination = TextField()
    date = DateField()  # Теперь NOT NULL
    timestamp = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        table_name = "search_history"

def init_db():
    db.connect()
    db.create_tables([SearchHistory], safe=True)
    db.close()