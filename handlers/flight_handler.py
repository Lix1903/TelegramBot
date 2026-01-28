from loader import bot
from utils.api import search_cheap_flights, get_weather, validate_date, normalize_iata
from database.queries import add_search
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# Обратное соответствие IATA-кодов для восстановления названий городов
IATA_REVERSE_MAP = {
    "MOW": "MOSCOW", "LED": "SAINT-PETERSBURG", "AER": "SOCHI",
    "SVX": "YEKATERINBURG", "KZN": "KAZAN", "IST": "ISTANBUL",
    "MAD": "MADRID", "BCN": "BARCELONA", "CDG": "PARIS", "LON": "LONDON"
}

def reverse_iata_lookup(iata_code: str) -> str:
    """Преобразует IATA-код в английское название города"""
    return IATA_REVERSE_MAP.get(iata_code.upper(), iata_code)


def shorten_callback_data(origin, dest, depart_date, return_date):
    """
    Создаёт короткую строку для callback_data.
    Формат: sort|asc|MOW|IST|080326|150326
    """
    from_iata = normalize_iata(origin)
    to_iata = normalize_iata(dest)

    # Разбиваем дату и пересобираем как ДДММГГ
    dep_parts = depart_date.split("-")  # ['2026', '03', '08']
    dep_short = dep_parts[2] + dep_parts[1] + dep_parts[0][2:]  # 08 + 03 + 26 = 080326

    ret_short = "OW"
    if return_date:
        ret_parts = return_date.split("-")
        ret_short = ret_parts[2] + ret_parts[1] + ret_parts[0][2:]  # 150326

    # Явно указываем 'asc' по умолчанию
    data = f"sort|asc|{from_iata}|{to_iata}|{dep_short}|{ret_short}"
    return data[:64]  # Увеличили до 64, чтобы влезло


def parse_callback_data(data: str):
    """
    Парсит callback_data и возвращает параметры сортировки.
    Возвращает: (sort_type, origin, destination, depart_date, return_date)
    """
    try:
        parts = data.split("|")
        if len(parts) < 6:
            return None

        # Теперь sort_type — это parts[1], так как parts[0] = 'sort'
        sort_type = "asc" if parts[1] == "asc" else "desc"
        from_iata = parts[2]
        to_iata = parts[3]
        dep_short = parts[4]  # 080326
        ret_short = parts[5]  # 150326 или OW

        # Исправленный парсинг дат: 080326 → 2026-03-08
        day = dep_short[:2]      # 08
        month = dep_short[2:4]   # 03
        year = "20" + dep_short[4:6]  # 26 → 2026
        depart_date = f"{year}-{month}-{day}"

        return_date = None
        if ret_short != "OW" and len(ret_short) == 6:
            return_day = ret_short[:2]
            return_month = ret_short[2:4]
            return_year = "20" + ret_short[4:6]
            return_date = f"{return_year}-{return_month}-{return_day}"

        # Преобразуем IATA обратно в название города на английском
        origin_city = reverse_iata_lookup(from_iata)
        dest_city = reverse_iata_lookup(to_iata)

        return sort_type, origin_city, dest_city, depart_date, return_date
    except Exception as e:
        print(f"❌ Ошибка разбора callback_data: {e}")
        return None


@bot.message_handler(func=lambda m: m.text == "Поиск авиабилетов")
def ask_origin_roundtrip(message):
    bot.send_message(message.chat.id, "🌆 Введите город вылета (например, Москва или MOW):")
    bot.register_next_step_handler(message, get_destination_roundtrip)


def get_destination_roundtrip(message):
    origin = message.text.strip()
    print(f"город вылета: {origin}")
    bot.send_message(message.chat.id, "🌆 Введите город прилёта:")
    bot.register_next_step_handler(message, lambda m: ask_depart_date(m, origin))


def ask_depart_date(message, origin):
    destination = message.text.strip()
    print(f"город прилёта: {destination}")
    bot.send_message(message.chat.id, "📅 Введите дату вылета (ГГГГ-ММ-ДД):")
    bot.register_next_step_handler(message, lambda m: ask_return_date(m, origin, destination))


def ask_return_date(message, origin, destination):
    depart_date = message.text.strip()
    if not validate_date(depart_date):
        bot.send_message(message.chat.id, "❌ Неверный формат даты. Введите в формате ГГГГ-ММ-ДД.")
        bot.send_message(message.chat.id, "📅 Повторите ввод даты вылета:")
        bot.register_next_step_handler(message, lambda m: ask_return_date(m, origin, destination))
        return
    bot.send_message(message.chat.id, "📅 Введите дату возврата (ГГГГ-ММ-ДД) или отправьте '-' если не нужно:")
    bot.register_next_step_handler(message, lambda m: show_flight_results(m, origin, destination, depart_date))


def show_flight_results(message, origin, destination, depart_date):
    return_date_input = message.text.strip()
    return_date = None
    if return_date_input != "-":
        if validate_date(return_date_input):
            return_date = return_date_input
        else:
            bot.send_message(message.chat.id, "⚠️ Неверный формат даты возврата. Будет найден билет только туда.")

    user_id = message.chat.id
    bot.send_message(user_id, "🔍 Ищу самые дешёвые авиабилеты...")

    flights = search_cheap_flights(
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        return_date=return_date
    )

    if not flights:
        bot.send_message(user_id, "❌ К сожалению, не удалось найти авиабилеты по вашему запросу.")
        return

    # Сохраняем запрос в БД
    add_search(user_id, origin, destination, depart_date, return_date or "")

    # Погода
    weather_from = get_weather(origin)
    weather_to = get_weather(destination)
    bot.send_message(user_id, f"🛫 Погода в {origin}: {weather_from}")
    bot.send_message(user_id, f"🛬 Погода в {destination}: {weather_to}")

    # Отправляем топ-3 результата
    for i, flight in enumerate(flights[:3], 1):
        price = flight.get('price', 'Не указана')
        depart = flight.get('departure_at', '—').split('T')[0]
        return_d = flight.get('return_at', '—')
        if return_d:
            return_d = return_d.split('T')[0]

        buy_link = flight.get('url')

        text = (f"{i}. ✈️ <b>Рейс туда и обратно</b>\n"
                f"   📅 Вылет: {depart}\n"
                f"   📅 Возврат: {return_d}\n"
                f"   💸 <b>{price} ₽</b>\n"
                f"   🔗 <a href='{buy_link}'>Купить этот билет</a>")
        bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)

    # Логируем перед созданием кнопок
    print(f"🔧 [КНОПКИ] depart_date={depart_date}, return_date={return_date}")
    base_data = shorten_callback_data(origin, destination, depart_date, return_date)
    print(f"🔧 [КНОПКИ] callback_data (base): {base_data}")

    # Кнопки сортировки — используем корректные данные
    markup = InlineKeyboardMarkup()

    # Создаём базовую строку и заменяем только нужное
    btn_asc = InlineKeyboardButton("📉 Дешевле", callback_data=base_data.replace("|asc|", "|asc|"))
    btn_desc = InlineKeyboardButton("📈 Дороже", callback_data=base_data.replace("|asc|", "|desc|"))

    markup.row(btn_asc, btn_desc)
    bot.send_message(user_id, "📊 Хотите отсортировать результаты?", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("sort|"))
def sort_flights_callback(call):
    # Логируем сырые данные
    print(f"🔧 [RAW] Исходные данные: {call.data}")

    parsed = parse_callback_data(call.data)
    if not parsed:
        bot.send_message(call.message.chat.id, "❌ Не удалось обработать запрос.")
        return

    sort_type, origin, destination, depart_date, return_date = parsed
    user_id = call.message.chat.id

    # Логируем для отладки
    print(f"🔍 [СОРТИРОВКА] Тип: {sort_type}, Параметры: {origin} → {destination}, {depart_date} → {return_date}")

    # Проверка, что дата вылета не в прошлом
    today = datetime.now().date()
    try:
        dep_date_obj = datetime.fromisoformat(depart_date).date()
        print(f"📅 Дата вылета: {dep_date_obj}, Сегодня: {today}")
        if dep_date_obj < today:
            bot.send_message(user_id, f"❌ Дата вылета ({depart_date}) не может быть в прошлом. Попробуйте снова.")
            return
    except ValueError as e:
        print(f"❌ Ошибка парсинга даты: {e}")
        bot.send_message(user_id, "❌ Некорректная дата вылета.")
        return

    bot.edit_message_text("🔄 Пересортировка...", user_id, call.message.message_id)

    flights = search_cheap_flights(
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        return_date=return_date
    )

    if not flights:
        bot.send_message(user_id, "❌ Не удалось получить данные для сортировки.")
        return

    # Убедимся, что сортировка работает правильно
    reverse = sort_type == "desc"
    sorted_flights = sorted(flights, key=lambda x: x.get('price', 0), reverse=reverse)

    # Логируем цены для отладки
    prices = [f.get('price') for f in flights]
    print(f"💰 Цены до сортировки: {prices}")
    sorted_prices = sorted(prices, reverse=reverse)
    print(f"📊 Цены после сортировки: {sorted_prices}")

    for i, f in enumerate(sorted_flights[:3], 1):
        price = f.get('price', 'Не указана')
        depart = f.get('departure_at', '—').split('T')[0]
        return_d = f.get('return_at', '—')
        if return_d:
            return_d = return_d.split('T')[0]
        buy_link = f.get('url')

        direction = "дороже" if reverse else "дешевле"
        text = (f"{i}. ✈️ <b>Отсортировано: {direction}</b>\n"
                f"   📅 {depart} → {return_d}\n"
                f"   💸 <b>{price} ₽</b>\n"
                f"   🔗 <a href='{buy_link}'>Купить</a>")
        bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)