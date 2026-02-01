from loader import bot
from utils.api import get_weather


@bot.message_handler(func=lambda message: message.text == "🌤 Погода")
def request_city_for_weather(message):
    bot.send_message(message.chat.id, "Введите название города, чтобы узнать погоду:")


@bot.message_handler(func=lambda message: message.text and message.text not in ["🌤 Погода"])
def show_weather(message):
    city = message.text.strip()
    
    # Проверка на пустое название города
    if not city or city.isdigit():
        bot.send_message(message.chat.id, "❌ Название города не может быть пустым или состоять только из цифр. Пожалуйста, введите корректное название города.")
        return
    
    bot.send_message(message.chat.id, f"🔍 Определяем погоду в городе **{city}**...")

    weather = get_weather(city)

    if weather in ["город не найден", "недоступна", "ошибка получения"]:
        bot.send_message(message.chat.id,
                         f"❌ Не удалось получить погоду для города *{city}*. Проверьте название и попробуйте снова.")
    else:
        bot.send_message(message.chat.id, f"🌤 *Погода в {city}:* \n{weather}", parse_mode="Markdown")