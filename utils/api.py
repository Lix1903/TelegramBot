import requests
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TRAVEL_TOKEN = os.getenv('TRAVEL_TOKEN')
WEATHER_KEY = os.getenv('WEATHER_KEY')

# Путь к JSON-файлу для сохранения ответа API
JSON_FILE_PATH = 'data/flights_response.json'

# Создаем папку, если её нет
os.makedirs(os.path.dirname(JSON_FILE_PATH), exist_ok=True)

# Расширенный IATA-справочник
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
    # Добавим ещё популярные
    "BERLIN": "BER", "AMSTERDAM": "AMS", "VIENNA": "VIE",
    "DUBAI": "DXB", "TOKYO": "TYO", "BEIJING": "PEK",
    "NEW YORK": "NYC", "LOS ANGELES": "LAX", "CHICAGO": "ORD"
}

def normalize_iata(city: str) -> str:
    """
    Преобразует название города в IATA-код.
    """
    upper_city = city.strip().upper()
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

def save_to_json(data: dict):
    """
    Сохраняет данные в JSON-файл.
    """
    try:
        with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"✅ Ответ API сохранён в {JSON_FILE_PATH}")
    except Exception as e:
        print(f"❌ Ошибка при сохранении в JSON: {e}")

def load_from_json() -> dict:
    """
    Загружает данные из JSON-файла.
    Возвращает пустой словарь, если файла нет.
    """
    try:
        if os.path.exists(JSON_FILE_PATH):
            with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✅ Данные загружены из {JSON_FILE_PATH}")
            return data
        else:
            print(f"⚠️ Файл {JSON_FILE_PATH} не найден. Будет создан при следующем сохранении.")
    except Exception as e:
        print(f"❌ Ошибка при чтении JSON: {e}")
    return {}

def search_cheap_flights(origin: str, destination: str, depart_date: str, return_date: str = None):
    """
    Поиск дешёвых авиабилетов через Aviasales API v3.
    Сохраняет полный ответ API в JSON и берёт ссылку 'link' как есть.

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

        # Сохраняем весь ответ API в JSON
        save_to_json(data)

        if not data.get('data'):
            print("❌ Нет рейсов, найденных по вашему запросу.")
            return []

        flights = []
        for item in data['data']:
            # Берём ссылку напрямую из поля 'link', без изменений
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
                'url': final_url  # Оригинальная ссылка из 'link'
            }
            flights.append(flight_data)
        return flights

    except requests.exceptions.Timeout:
        print("❌ Ошибка: таймаут при запросе к API.")
        # При ошибке — используем кэш
        cached_data = load_from_json()
        if cached_data:
            print("⚠️ Используем кэшированные данные из JSON")
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
        w_resp = requests.get(weather_url, params=w_params, timeout=10)
        w_resp.raise_for_status()
        w = w_resp.json()

        temp = round(w['main']['temp'])
        desc = w['weather'][0]['description'].capitalize()
        result = f"🌡 {temp}°C, {desc}"

        get_weather.cache[city] = result
        return result

    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка API погоды: {e}")
        return "ошибка получения"
    except Exception as e:
        print(f"❌ Ошибка обработки погоды: {e}")
        return "недоступна"