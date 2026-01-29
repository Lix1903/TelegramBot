from peewee import  Model, TextField, DateTimeField
from datetime import datetime
from .db import db


class ApiFlightResponse(Model):
    origin = TextField()
    destination = TextField()
    depart_date = TextField()
    return_date = TextField(null=True)
    response_json = TextField()
    created_at = DateTimeField(default=datetime.now)
    search_hash = TextField(unique=True)

    class Meta:
        database = db
        table_name = "api_flight_responses"