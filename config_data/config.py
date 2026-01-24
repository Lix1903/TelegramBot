import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_KEY = os.getenv("WEATHER_KEY")
TRAVEL_TOKEN = os.getenv("TRAVEL_TOKEN")

if not all([BOT_TOKEN, WEATHER_KEY, TRAVEL_TOKEN]):
    raise ValueError("Не все токены найдены в .env")