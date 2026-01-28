import requests
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import sqlite3
from contextlib import contextmanager

load_dotenv()

TRAVEL_TOKEN = os.getenv('TRAVEL_TOKEN')
WEATHER_KEY = os.getenv('WEATHER_KEY')

# Путь к общей базе данных
DB_PATH = 'history.db'

@contextmanager
def get_db_connection():
    """Контекстный менеджер для подключения к общей БД"""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Создаёт таблицу для хранения ответов API при первом запуске"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_flight_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                depart_date TEXT NOT NULL,
                return_date TEXT,
                response_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                search_hash TEXT UNIQUE
            )
        ''')
        conn.commit()

def normalize_iata(city: str) -> str:
    """
    Преобразует название города в IATA-код.
    """
    upper_city = city.strip().upper()
    IATA_MAP = {
        "MOSCOW": "MOW", "MOW": "MOW", "MOSKVA": "MOW", "МОСКВА": "MOW",
        "SAINT-PETERSBURG": "LED", "LED": "LED", "САНКТ-ПЕТЕРБУРГ": "LED",
        "SOCHI": "AER", "AER": "AER", "СОЧИ": "AER",
        "YEKATERINBURG": "SVX", "SVX": "SVX", "ЕКАТЕРИНБУРГ": "SVX",
        "KAZAN": "KZN", "KZN": "KZN", "КАЗАНЬ": "KZN",
        "ISTANBUL": "IST", "IST": "IST", "СТАМБУЛ": "IST",
        "MADRID": "MAD", "MAD": "MAD", "МАДРИД": "MAD",
        "BARCELONA": "BCN", "BCN": "BCN", "БАРСЕЛОНА": "BCN",
        "PARIS": "CDG", "CDG": "CDG", "ПАРИЖ": "CDG",
        "LONDON": "LON", "LON": "LON",
        "BERLIN": "BER", "AMSTERDAM": "AMS", "VIENNA": "VIE",
        "DUBAI": "DXB", "TOKYO": "TYO", "BEIJING": "PEK",
        "NEW YORK": "NYC", "LOS ANGELES": "LAX", "CHICAGO": "ORD"
    }
    return IATA_MAP.get(upper_city, upper_city[:3].upper())

def validate_date(date_str: str) -> bool:
    """
    Проверяет, является ли строка корректной датой в формате ГГГГ-ММ-ДД.
    """
    try:
        datetime.fromisoformat(date_str)
        return True
    except ValueError:
        return False

def save_api_response_to_db(origin: str, destination: str, depart_date: str, return_date: str, response_data: dict):
    """
    Сохраняет ответ API в таблицу api_flight_responses с уникальным хешем.
    """
    search_hash = f"{origin}_{destination}_{depart_date}_{return_date or 'OW'}"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO api_flight_responses 
                (origin, destination, depart_date, return_date, response_json, search_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                origin,
                destination,
                depart_date,
                return_date,
                json.dumps(response_data, ensure_ascii=False, indent=2),
                search_hash
            ))
            conn.commit()
        print("✅ Ответ API сохранён в history.db")
    except Exception as e:
        print(f"❌ Ошибка при сохранении в БД: {e}")

def load_latest_api_response_from_db() -> dict:
    """
    Загружает последний успешный ответ API из БД.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT response_json FROM api_flight_responses
                ORDER BY created_at DESC LIMIT 1
            ''')
            row = cursor.fetchone()
            if row:
                print("✅ Последний ответ API загружен из БД")
                return json.loads(row[0])
            else:
                print("⚠️ Нет сохранённых ответов API в БД")
                return {}
    except Exception as e:
        print(f"❌ Ошибка при чтении из БД: {e}")
        return {}

def search_cheap_flights(origin: str, destination: str, depart_date: str, return_date: str = None):
    """
    Поиск дешёвых авиабилетов через Aviasales API v3.
    Сохраняет полный ответ API в history.db и берёт ссылку 'link' как есть.

    :param origin: Город вылета
    :param destination: Город прилёта
    :param depart_date: Дата вылета (ГГГГ-ММ-ДД)
    :param return_date: Дата возврата (ГГГГ-ММ-ДД), опционально
    :return: Список найденных рейсов с оригинальными ссылками из поля 'link'
    """
    # Валидация дат
    if not validate_date(depart_date):
        print(f"❌ Некорректная дата вылета: {depart_date}")
        return []

    # Автоматическое определение return_date, если не задан
    if not return_date:
        try:
            depart_dt = datetime.fromisoformat(depart_date)
            return_dt = depart_dt + timedelta(days=7)
            return_date = return_dt.strftime("%Y-%m-%d")
            print(f"📅 Дата возврата не указана. Установлена автоматически: {return_date}")
        except Exception as e:
            print(f"❌ Не удалось рассчитать дату возврата: {e}")
            return []

    origin_iata = normalize_iata(origin)
    dest_iata = normalize_iata(destination)

    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    params = {
        'origin': origin_iata,
        'destination': dest_iata,
        'departure_at': depart_date,
        'return_at': return_date,
        'one_way': 'false',
        'token': TRAVEL_TOKEN,
        'currency': 'RUB',
        'limit': 10,
        'page': 1,
        'sorting': 'price'
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Сохраняем весь ответ API в history.db
        save_api_response_to_db(origin, destination, depart_date, return_date, data)

        if not data.get('data'):
            print("❌ Нет рейсов, найденных по вашему запросу.")
            return []

        flights = []
        for item in data['data']:
            link = item.get('link')
            if not link or not link.startswith('/search/'):
                print(f"⚠️ Пропущен рейс: некорректная ссылка 'link' → {link}")
                continue

            final_url = f"https://www.aviasales.ru{link}"

            flight_data = {
                'price': item.get('price'),
                'airline': item.get('airline') or "Неизвестно",
                'departure_at': item.get('departure_at'),
                'return_at': item.get('return_at'),
                'transfers': item.get('transfers', 0),
                'url': final_url
            }
            flights.append(flight_data)
        return flights

    except requests.exceptions.Timeout:
        print("❌ Ошибка: таймаут при запросе к API.")
        # При ошибке — используем кэш из БД
        cached_data = load_latest_api_response_from_db()
        if cached_data:
            print("⚠️ Используем кэшированные данные из БД")
            return extract_flights_from_cache(cached_data)
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка HTTP-запроса: {e}")
    except Exception as e:
        print(f"❌ Непредвиденная ошибка: {e}")
    return []

def extract_flights_from_cache(data: dict) -> list:
    """
    Извлекает рейсы из закэшированных данных, используя поле 'link'.
    """
    flights = []
    for item in data.get('data', []):
        link = item.get('link')
        if not link or not link.startswith('/search/'):
            continue
        final_url = f"https://www.aviasales.ru{link}"
        flights.append({
            'price': item.get('price'),
            'airline': item.get('airline') or "Неизвестно",
            'departure_at': item.get('departure_at'),
            'return_at': item.get('return_at'),
            'transfers': item.get('transfers', 0),
            'url': final_url
        })
    return flights

def get_weather(city: str) -> str:
    """
    Получает текущую погоду в городе.
    Использует кэширование в памяти.
    """
    if not hasattr(get_weather, 'cache'):
        get_weather.cache = {}

    if city in get_weather.cache:
        print(f"🌤 Используем кэш для погоды: {city}")
        return get_weather.cache[city]

    try:
        geo_url = "https://api.openweathermap.org/geo/1.0/direct"
        geo_params = {'q': city, 'limit': 1, 'appid': WEATHER_KEY}
        geo_resp = requests.get(geo_url, params=geo_params, timeout=10)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()

        if not geo_data:
            result = "город не найден"
            get_weather.cache[city] = result
            return result

        lat, lon = geo_data[0]['lat'], geo_data[0]['lon']

        weather_url = "https://api.openweathermap.org/data/2.5/weather"
        w_params = {
            'lat': lat,
            'lon': lon,
            'appid': WEATHER_KEY,
            'units': 'metric',
            'lang': 'ru'
        }
        w_resp = requests.get(weather_url, params=w_params, timeout=15)  # Увеличен таймаут до 15 секунд
        w_resp.raise_for_status()
        w = w_resp.json()

        temp = round(w['main']['temp'])
        desc = w['weather'][0]['description'].capitalize()
        result = f"🌡 {temp}°C, {desc}"

        get_weather.cache[city] = result
        return result

    except requests.exceptions.Timeout:
        print("⚠️ Таймаут при запросе к API погоды. Повторная попытка...")
        try:
            # Повторный запрос с увеличенным временем
            w_resp = requests.get(weather_url, params=w_params, timeout=20)
            w_resp.raise_for_status()
            w = w_resp.json()
            temp = round(w['main']['temp'])
            desc = w['weather'][0]['description'].capitalize()
            result = f"🌡 {temp}°C, {desc}"
            get_weather.cache[city] = result
            return result
        except Exception:
            return "ошибка получения (таймаут)"
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка API погоды: {e}")
        return "ошибка получения"
    except Exception as e:
        print(f"❌ Ошибка обработки погоды: {e}")
        return "недоступна"