from loader import bot
from keyboards.reply import main_menu
from utils.api import search_cheap_roundtrip, get_weather
from database.queries import add_search
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import re


@bot.message_handler(func=lambda m: m.text == "Поиск авиабилетов")
def ask_origin_roundtrip(message):
    print("🎉 КНОПКА 'Поиск авиабилетов' РАСПОЗНАНА!")
    bot.send_message(message.chat.id, "🌆 Введите город вылета (например, Москва или MOW):")
    bot.register_next_step_handler(message, get_destination_roundtrip)

def get_destination_roundtrip(message):
    origin = message.text.strip()
    print(f"город вылета: {origin}")
    bot.send_message(message.chat.id, "🌆 Введите город прилёта:")
    bot.register_next_step_handler(message, lambda m: ask_depart_month(m, origin))

def ask_depart_month(message, origin):
    destination = message.text.strip()
    print(f"город прилёта: {destination}")
    bot.send_message(message.chat.id, "📅 Введите месяц вылета (ГГГГ-ММ):")
    bot.register_next_step_handler(message, lambda m: ask_return_month(m, origin, destination))

def ask_return_month(message, origin, destination):
    depart_month = message.text.strip()
    is_valid, error = validate_date_month(depart_month)
    if not is_valid:
        bot.send_message(message.chat.id, error)
        bot.send_message(message.chat.id, "📅 Повторите ввод месяца вылета:")
        bot.register_next_step_handler(message, lambda m: ask_return_month(m, origin, destination))
        return
    bot.send_message(message.chat.id, "📅 Введите месяц возвращения (ГГГГ-ММ, можно пропустить):")
    bot.register_next_step_handler(message, lambda m: show_roundtrip_results(m, origin, destination, depart_month))

def show_roundtrip_results(message, origin, destination, depart_month):
    return_month = message.text.strip()
    if return_month and not validate_date_month(return_month)[0]:
        return_month = ""

    user_id = message.chat.id
    bot.send_message(user_id, "🔍 Ищу самые дешёвые билеты туда-обратно...")

    flights = search_cheap_roundtrip(origin, destination, depart_month, return_month)
    if not flights:
        bot.send_message(user_id, "❌ Билеты не найдены. Проверьте город и даты.")
        return

    # Сохраняем с месяцами (не датами)
    add_search(user_id, origin, destination, depart_month, return_month)

    # Погода
    weather_from = get_weather(origin)
    weather_to = get_weather(destination)
    bot.send_message(user_id, f"🛫 Погода в {origin}: {weather_from}")
    bot.send_message(user_id, f"🛬 Погода в {destination}: {weather_to}")

    # Отправляем топ-3
    for i, flight in enumerate(flights[:3], 1):
        price = flight.get('price', 'Не указана')
        depart = flight.get('depart_date', '—')
        return_date = flight.get('return_date', '—')
        link = f"https://www.aviasales.ru{flight.get('url', '')}"

        text = (f"{i}. ✈️ <b>Туда-обратно</b>\n"
                f"   📅 Вылет: {depart[:10]}\n"
                f"   📅 Возврат: {return_date[:10]}\n"
                f"   💸 <b>{price} ₽</b>\n"
                f"   🔗 <a href='{link}'>Купить</a>")
        bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)

    # Кнопки сортировки
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📉 Дешевле", callback_data=f"sort_price_asc|{origin}|{destination}|{depart_month}|{return_month}"),
        InlineKeyboardButton("📈 Дороже", callback_data=f"sort_price_desc|{origin}|{destination}|{depart_month}|{return_month}")
    )
    bot.send_message(user_id, "📊 Отсортировать результаты?", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("sort_"))
def sort_flights_callback(call):
    data = call.data.split("|")
    sort_type = data[0]
    origin, dest, depart_m, return_m = data[1], data[2], data[3], data[4]
    user_id = call.message.chat.id
    bot.edit_message_text("🔄 Пересортировка...", user_id, call.message.message_id)
    flights = search_cheap_roundtrip(origin, dest, depart_m, return_m)
    if not flights:
        bot.send_message(user_id, "❌ Нет данных.")
        return
    reverse = "desc" in sort_type
    sorted_flights = sorted(flights, key=lambda x: x.get('price', 0), reverse=reverse)
    for i, f in enumerate(sorted_flights[:3], 1):
        price = f.get('price', 'Не указана')
        depart = f.get('depart_date', '—')
        return_d = f.get('return_date', '—')
        link = f"https://www.aviasales.ru{f.get('url', '')}"
        text = (f"{i}. ✈️ <b>Отсортировано: {'дороже' if reverse else 'дешевле'}</b>\n"
                f"   📅 {depart[:10]} → {return_d[:10]}\n"
                f"   💸 <b>{price} ₽</b>\n"
                f"   🔗 <a href='{link}'>Купить</a>")
        bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)

def validate_date_month(date_text: str) -> tuple[bool, str]:
    if not re.match(r'^\d{4}-\d{2}$', date_text):
        return False, "❌ Формат: ГГГГ-ММ (например, 2025-12)"
    return True, "ok"
