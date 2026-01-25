import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

TRAVEL_TOKEN = os.getenv('TRAVEL_TOKEN')
WEATHER_KEY = os.getenv('WEATHER_KEY')

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

def search_cheap_flights(origin: str, destination: str, depart_date: str, return_date: str = None):
    """
    Поиск дешёвых авиабилетов через Aviasales API v3.
    Всегда ищет round-trip (one_way=false), но если return_date не указан — ставит +7 дней.

    :param origin: Город вылета
    :param destination: Город прилёта
    :param depart_date: Дата вылета (ГГГГ-ММ-ДД)
    :param return_date: Дата возврата (ГГГГ-ММ-ДД), опционально
    :return: Список найденных рейсов
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
        'one_way': 'false',  # ВСЕГДА ищем туда и обратно
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

        if not data.get('data'):
            print("❌ Нет рейсов, найденных по вашему запросу.")
            return []

        flights = []
        for item in data['data']:
            flight_data = {
                'price': item.get('price'),
                'airline': item.get('airline') or "Неизвестно",
                'departure_at': item.get('departure_at'),
                'return_at': item.get('return_at'),
                'transfers': item.get('transfers', 0),
                'url': f"https://www.aviasales.ru{item.get('url', '')}"
            }
            flights.append(flight_data)
        return flights

    except requests.exceptions.Timeout:
        print("❌ Ошибка: таймаут при запросе к API.")
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка HTTP-запроса: {e}")
    except Exception as e:
        print(f"❌ Непредвиденная ошибка при обработке ответа: {e}")
    return []

def get_weather(city: str) -> str:
    """
    Получает текущую погоду в городе.
    Использует кэширование в памяти (упрощённое).
    """
    # Простое кэширование (в реальном проекте используй Redis или файл)
    if not hasattr(get_weather, 'cache'):
        get_weather.cache = {}

    if city in get_weather.cache:
        print(f"🌤 Используем кэш для погоды: {city}")
        return get_weather.cache[city]

    try:
        # Шаг 1: Получить координаты
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

        # Шаг 2: Получить погоду
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

        # Сохраняем в кэш
        get_weather.cache[city] = result
        return result

    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка API погоды: {e}")
        return "ошибка получения"
    except Exception as e:
        print(f"❌ Ошибка обработки погоды: {e}")
        return "недоступна"