import requests
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database.models import ApiFlightResponse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

TRAVEL_TOKEN = os.getenv('TRAVEL_TOKEN')
WEATHER_KEY = os.getenv('WEATHER_KEY')


def get_cities_iata(query: str) -> dict:
    """
    Получает IATA-коды городов отправления и назначения с помощью TravelPayouts widgets API.
    Поддерживает запросы вида "Из Москвы в Лондон" и определение столиц по странам.
    
    Args:
        query: Поисковая фраза на русском языке (например, "Из Москвы в Лондон")
    
    Returns:
        Словарь с ключами 'origin' и 'destination' и их IATA-кодами,
        или пустой словарь при ошибке
    """
    try:
        url = "https://www.travelpayouts.com/widgets_suggest_params"
        params = {
            'q': query.strip()
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        result = {}
        if data.get('origin', {}).get('iata'):
            result['origin'] = data['origin']['iata']
        
        if data.get('destination', {}).get('iata'):
            result['destination'] = data['destination']['iata']
            
        if result:
            print(f"✅ Успешно получены IATA-коды: {result}")
            
        return result
        
    except Exception as e:
        print(f"❌ Не удалось получить IATA-коды через widgets API: {e}")
    
    return {}


def normalize_iata(city: str) -> str:
    """
    Преобразует название города в IATA-код.
    Сначала проверяет встроенный словарь, затем запрашивает через API.
    """
    upper_city = city.strip().upper()
    iata_map = {
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
        "NEW YORK": "NYC", "LOS ANGELES": "LAX", "CHICAGO": "ORD",
        "UFA": "UFA", "UF": "UFA", "УФА": "UFA"
    }
    
    # Сначала ищем в локальном словаре
    if upper_city in iata_map:
        return iata_map[upper_city]


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
    Сохраняет ответ API в таблицу ApiFlightResponse через Peewee.
    """
    search_hash = f"{origin}_{destination}_{depart_date}_{return_date or 'OW'}"
    try:
        ApiFlightResponse.create(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            response_json=json.dumps(response_data, ensure_ascii=False, indent=2),
            search_hash=search_hash + "_" + str(int(datetime.now().timestamp()))
        )
        print("✅ Ответ API сохранён в database/history.db (через Peewee)")
    except Exception as e:
        print(f"❌ Ошибка при сохранении в БД: {e}")


def load_latest_api_response_from_db() -> dict:
    """
    Загружает последний успешный ответ API из БД.
    """
    try:
        last_record = ApiFlightResponse.select().order_by(ApiFlightResponse.created_at.desc()).first()
        if last_record:
            print("✅ Последний ответ API загружен из БД")
            return json.loads(last_record.response_json)
        print("⚠️ Нет сохранённых ответов API в БД")
        return {}
    except Exception as e:
        print(f"❌ Ошибка при чтении из БД: {e}")
        return {}


def search_cheap_flights(origin: str, destination: str, depart_date: str, return_date: str = None):
    """
    Поиск дешёвых авиабилетов через Aviasales API v3.
    Сохраняет полный ответ API в history.db и берёт ссылку 'link' как есть.
    """
    if not validate_date(depart_date):
        print(f"❌ Некорректная дата вылета: {depart_date}")
        return []

    if not return_date:
        try:
            depart_dt = datetime.fromisoformat(depart_date)
            return_dt = depart_dt + timedelta(days=7)
            return_date = return_dt.strftime("%Y-%m-%d")
            print(f"📅 Дата возврата не указана. Установлена автоматически: {return_date}")
        except Exception as e:
            print(f"❌ Не удалось рассчитать дату возврата: {e}")
            return []

    # Сначала пробуем получить оба кода сразу через widgets API
    cities_data = get_cities_iata(f"Из {origin} в {destination}")
    
    origin_iata = cities_data.get('origin')
    if origin_iata:
        print(f"✅ Используем IATA-код {origin_iata} для города {origin} из widgets API")
    else:
        # Если widgets API не помог, используем обычный метод
        origin_iata = normalize_iata(origin)

    dest_iata = cities_data.get('destination')
    if dest_iata:
        print(f"✅ Используем IATA-код {dest_iata} для города {destination} из widgets API")
    else:
        # Если widgets API не помог, используем обычный метод
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

        save_api_response_to_db(origin, destination, depart_date, return_date, data)

        if not data.get('data'):
            print("❌ Нет рейсов, найденных по вашему запросу.")
            return []

        flights = []
        for item in data['data']:
            link = item.get('link')
            if not link or not link.startswith('/search/'):
                continue

            flight_data = {
                'price': item.get('price'),
                'airline': item.get('airline') or "Неизвестно",
                'departure_at': item.get('departure_at'),
                'return_at': item.get('return_at'),
                'transfers': item.get('transfers', 0),
                'url': f"https://www.aviasales.ru{link}"
            }
            flights.append(flight_data)
        return flights

    except requests.exceptions.Timeout:
        print("❌ Ошибка: таймаут при запросе к API.")
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
        flights.append({
            'price': item.get('price'),
            'airline': item.get('airline') or "Неизвестно",
            'departure_at': item.get('departure_at'),
            'return_at': item.get('return_at'),
            'transfers': item.get('transfers', 0),
            'url': f"https://www.aviasales.ru{link}"
        })
    return flights


def get_weather(city: str) -> str:
    """
    Получает текущую погоду в городе с retry и кэшированием координат.
    """
    weather_url = "https://api.openweathermap.org/data/2.5/weather"

    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    try:
        # Получение координат с retry
        geo_url = "https://api.openweathermap.org/geo/1.0/direct"
        geo_params = {'q': city, 'limit': 1, 'appid': WEATHER_KEY}
        geo_resp = session.get(geo_url, params=geo_params, timeout=30)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()

        if not geo_data:
            return "город не найден"

        lat, lon = geo_data[0]['lat'], geo_data[0]['lon']

        # Запрос погоды
        w_params = {
            'lat': lat,
            'lon': lon,
            'appid': WEATHER_KEY,
            'units': 'metric',
            'lang': 'ru'
        }

        w_resp = session.get(weather_url, params=w_params, timeout=30)
        w_resp.raise_for_status()
        w = w_resp.json()

        temp = round(w['main']['temp'])
        desc = w['weather'][0]['description'].capitalize()
        return f"🌡 {temp}°C, {desc}"

    except requests.exceptions.Timeout:
        return "ошибка получения (таймаут)"
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка API погоды: {e}")
        return "ошибка получения"
    except (KeyError, IndexError, TypeError) as e:
        print(f"❌ Ошибка парсинга: {e}")
        return "недоступна"
    except Exception as e:
        print(f"❌ Необработанная ошибка: {e}")
        return "недоступна"