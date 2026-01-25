from loader import bot
from utils.api import search_cheap_flights, get_weather, validate_date, normalize_iata
from database.queries import add_search
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import re


def build_aviasales_direct_link(origin: str, destination: str, depart_date: str, return_date: str = None) -> str:
    """
    Генерирует корректную ссылку Aviasales с поддержкой one_way.
    """
    try:
        # Преобразуем даты: 2026-02-22 → 220226 (ДДММГГ)
        def date_to_dmmyy(d: str) -> str:
            return re.sub(r"(\d{4})-(\d{2})-(\d{2})", r"\3\2\1", d)[2:]

        from_iata = normalize_iata(origin)
        to_iata = normalize_iata(destination)
        depart_part = date_to_dmmyy(depart_date)

        # Если нет даты возврата — one_way
        if not return_date:
            route = f"{from_iata}{to_iata}{depart_part}"
            return f"https://www.aviasales.ru/search/{route}?currency=RUB&one_way=true"

        # Иначе — туда и обратно
        return_part = date_to_dmmyy(return_date)
        route = f"{from_iata}{to_iata}{depart_part}{to_iata}{from_iata}{return_part}"
        return f"https://www.aviasales.ru/search/{route}?currency=RUB"

    except Exception as e:
        print(f"❌ Ошибка генерации ссылки: {e}")
        return "https://www.aviasales.ru"

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

        # Основная логика ссылки
        ticket_url = flight.get('url')
        if ticket_url and ticket_url.startswith('/'):
            direct_link = f"https://www.aviasales.ru{ticket_url}"
        else:
            # Если API не дал хорошей ссылки — генерируем вручную
            direct_link = build_aviasales_direct_link(origin, destination, depart_date, return_date)

        text = (f"{i}. ✈️ <b>Рейс туда и обратно</b>\n"
                f"   📅 Вылет: {depart}\n"
                f"   📅 Возврат: {return_d}\n"
                f"   💸 <b>{price} ₽</b>\n"
                f"   🔗 <a href='{direct_link}'>Купить этот билет</a>")
        bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)

    # Кнопки сортировки
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📉 Дешевле",
                             callback_data=f"sort_price_asc|{origin}|{destination}|{depart_date}|{return_date or ''}"),
        InlineKeyboardButton("📈 Дороже",
                             callback_data=f"sort_price_desc|{origin}|{destination}|{depart_date}|{return_date or ''}")
    )
    bot.send_message(user_id, "📊 Хотите отсортировать результаты?", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("sort_"))
def sort_flights_callback(call):
    data = call.data.split("|")
    sort_type = data[0]
    origin, dest, depart_date, return_date = data[1], data[2], data[3], data[4] if len(data) > 4 else ""

    user_id = call.message.chat.id
    bot.edit_message_text("🔄 Пересортировка результатов...", user_id, call.message.message_id)

    flights = search_cheap_flights(
        origin=origin,
        destination=dest,
        depart_date=depart_date,
        return_date=return_date if return_date != "" else None
    )

    if not flights:
        bot.send_message(user_id, "❌ Не удалось получить данные для сортировки.")
        return

    reverse = "desc" in sort_type
    sorted_flights = sorted(flights, key=lambda x: x.get('price', 0), reverse=reverse)

    for i, f in enumerate(sorted_flights[:3], 1):
        price = f.get('price', 'Не указана')
        depart = f.get('departure_at', '—').split('T')[0]
        return_d = f.get('return_at', '—')
        if return_d:
            return_d = return_d.split('T')[0]

        ticket_url = f.get('url')
        if ticket_url and ticket_url.startswith('/'):
            direct_link = f"https://www.aviasales.ru{ticket_url}"
        else:
            direct_link = build_aviasales_direct_link(origin, dest, depart_date, return_date)

        text = (f"{i}. ✈️ <b>Отсортировано: {'дороже' if reverse else 'дешевле'}</b>\n"
                f"   📅 {depart} → {return_d}\n"
                f"   💸 <b>{price} ₽</b>\n"
                f"   🔗 <a href='{direct_link}'>Купить этот билет</a>")
        bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)