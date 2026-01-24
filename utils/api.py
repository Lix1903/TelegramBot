import requests
import os
from dotenv import load_dotenv

load_dotenv()

TRAVEL_TOKEN = os.getenv('TRAVEL_TOKEN')
WEATHER_KEY = os.getenv('WEATHER_KEY')

# Упрощённый IATA-справочник
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
    "LONDON": "LON", "LON": "LON"
}

def normalize_iata(city: str) -> str:
    upper_city = city.strip().upper()
    return IATA_MAP.get(upper_city, upper_city[:3])

def search_cheap_roundtrip(origin: str, destination: str, depart_month: str, return_month: str = ""):
    origin_iata = normalize_iata(origin)
    dest_iata = normalize_iata(destination)

    url = "http://api.travelpayouts.com/v1/prices/cheap"
    params = {
        'origin': origin_iata,
        'destination': dest_iata,
        'depart_date': depart_month,
        'token': TRAVEL_TOKEN,
        'currency': 'RUB',
        'page': 1
    }

    if return_month:
        params['return_date'] = return_month

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data'):
                flights = []
                for key, flight in data['data'].items():
                    # Убедимся, что есть все нужные поля
                    if not flight.get('price'):
                        continue
                    if not flight.get('depart_date') or not flight.get('return_date'):
                        continue
                    if not flight.get('url'):
                        flight['url'] = ''
                    flights.append(flight)
                return flights
            else:
                print("❌ Нет рейсов в ответе API")
                return []
        else:
            print(f"❌ Aviasales API error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return []

def get_weather(city: str):
    try:
        geo_url = "https://api.openweathermap.org/geo/1.0/direct"
        geo_params = {'q': city, 'appid': WEATHER_KEY, 'limit': 1}
        geo_resp = requests.get(geo_url, params=geo_params, timeout=10)

        if geo_resp.status_code != 200 or not geo_resp.json():
            return "недоступна"

        lat, lon = geo_resp.json()[0]['lat'], geo_resp.json()[0]['lon']

        weather_url = "https://api.openweathermap.org/data/2.5/weather"
        w_params = {
            'lat': lat, 'lon': lon,
            'appid': WEATHER_KEY,
            'units': 'metric', 'lang': 'ru'
        }
        w_resp = requests.get(weather_url, params=w_params, timeout=10)

        if w_resp.status_code == 200:
            w = w_resp.json()
            temp = w['main']['temp']
            desc = w['weather'][0]['description'].capitalize()
            return f"🌡 {temp}°C, {desc}"
    except Exception as e:
        print(f"❌ Ошибка погоды: {e}")
    return "недоступна"