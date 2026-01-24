from loader import bot
from keyboards.reply import main_menu
from database.queries import *
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        "✈️🌤 Привет! Я помогу найти дешёвые авиабилеты и узнать погоду.",
        reply_markup=main_menu()
    )


# @bot.message_handler(func=lambda message: True)
# def echo_all(message):
#     print(f"📨 Бот получил сообщение: '{message.text}' от {message.chat.id}")
#     if message.text == "Поиск авиабилетов":
#         print("✅ Кнопка 'Поиск авиабилетов' распознана!")
#     else:
#         bot.reply_to(message, f"Я получил: {message.text}\nНажми /start")


@bot.message_handler(func=lambda m: m.text == "📚 История")
def show_history(message):
    user_id = message.chat.id
    history = get_history(user_id)
    if not history:
        bot.send_message(user_id, "📅 История пуста.")
        return
    text = "📌 Последние запросы:\n\n"
    for h in history:
        text += f"🛫 {h.departure} → {h.destination}\n⏰ {h.timestamp.strftime('%d.%m %H:%M')}\n\n"
    bot.send_message(user_id, text)

@bot.message_handler(func=lambda m: m.text == "🗑 Очистить историю")
def confirm_clear(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Да", callback_data="confirm_clear"),
        InlineKeyboardButton("❌ Нет", callback_data="cancel_clear")
    )
    bot.send_message(message.chat.id, "Удалить историю?", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "confirm_clear")
def do_clear(callback):
    user_id = callback.message.chat.id
    count = clear_history(user_id)
    bot.edit_message_text(f"✅ Удалено {count} записей.", user_id, callback.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "cancel_clear")
def cancel_clear(callback):
    bot.edit_message_text("❌ Отменено.", callback.message.chat.id, callback.message.message_id)