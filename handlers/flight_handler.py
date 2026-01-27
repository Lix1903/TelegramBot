from loader import bot
from utils.api import search_cheap_flights, get_weather, validate_date
from database.queries import add_search
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


# Функция для сокращения IATA и дат
def shorten_callback_data(origin, dest, depart_date, return_date):
    # Берём первые 3 символа и делаем заглавными
    from_iata = origin.strip().upper()[:3]
    to_iata = dest.strip().upper()[:3]
    # Дата: 2026-02-22 → 220226
    dep_short = depart_date.replace("-", "")[2:]
    ret_short = return_date.replace("-", "")[2:] if return_date else "OW"

    data = f"sort|{from_iata}|{to_iata}|{dep_short}|{ret_short}"
    if len(data) > 60:
        # На всякий случай обрезаем
        return data[:60]
    return data


# Распаковка данных
def parse_callback_data(data: str):
    try:
        parts = data.split("|")
        if len(parts) < 5:
            return None
        sort_type = "asc" if "asc" in parts[0] else "desc"
        from_iata = parts[1]
        to_iata = parts[2]
        dep_short = parts[3]  # 220226
        ret_short = parts[4]  # 290226 или OW

        # Восстанавливаем полные даты
        depart_date = f"20{dep_short[4:]}-{dep_short[2:4]}-{dep_short[:2]}"
        return_date = None if ret_short == "OW" else f"20{ret_short[4:]}-{ret_short[2:4]}-{ret_short[:2]}"

        return sort_type, from_iata, to_iata, depart_date, return_date
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

    # Кнопки сортировки — используем короткие данные
    markup = InlineKeyboardMarkup()
    btn_asc = InlineKeyboardButton("📉 Дешевле", callback_data=shorten_callback_data(origin, destination, depart_date, return_date))
    btn_desc = InlineKeyboardButton("📈 Дороже", callback_data=shorten_callback_data(origin, destination, depart_date, return_date).replace("asc", "desc"))
    markup.row(btn_asc, btn_desc)

    bot.send_message(user_id, "📊 Хотите отсортировать результаты?", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("sort|"))
def sort_flights_callback(call):
    parsed = parse_callback_data(call.data)
    if not parsed:
        bot.send_message(call.message.chat.id, "❌ Не удалось обработать запрос.")
        return

    sort_type, from_iata, to_iata, depart_date, return_date = parsed
    user_id = call.message.chat.id

    bot.edit_message_text("🔄 Пересортировка...", user_id, call.message.message_id)

    # Здесь нужно получить полные названия городов
    # Временно используем IATA как есть. В реальности можно хранить маппинг.
    flights = search_cheap_flights(
        origin=from_iata,
        destination=to_iata,
        depart_date=depart_date,
        return_date=return_date
    )

    if not flights:
        bot.send_message(user_id, "❌ Не удалось получить данные.")
        return

    reverse = sort_type == "desc"
    sorted_flights = sorted(flights, key=lambda x: x.get('price', 0), reverse=reverse)

    for i, f in enumerate(sorted_flights[:3], 1):
        price = f.get('price', 'Не указана')
        depart = f.get('departure_at', '—').split('T')[0]
        return_d = f.get('return_at', '—')
        if return_d:
            return_d = return_d.split('T')[0]
        buy_link = f.get('url')

        text = (f"{i}. ✈️ <b>Отсортировано: {'дороже' if reverse else 'дешевле'}</b>\n"
                f"   📅 {depart} → {return_d}\n"
                f"   💸 <b>{price} ₽</b>\n"
                f"   🔗 <a href='{buy_link}'>Купить</a>")
        bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)