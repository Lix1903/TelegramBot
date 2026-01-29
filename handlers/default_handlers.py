from loader import bot
from keyboards.reply import main_menu
from database.queries import *
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        "✈️🌤 Привет! Я помогу найти авиабилеты и узнать погоду.",
        reply_markup=main_menu()
    )


@bot.message_handler(commands=['help'])
def send_help(message: Message):
    help_text = (
        "ℹ️ <b>Справка по использованию бота</b>\n\n"
        "Доступные команды:\n"
        "/start — начать работу с ботом\n"
        "/help — показать это сообщение\n"
        "/search — начать поиск авиабилетов\n\n"

        "🔍 <b>Поиск авиабилетов</b>\n"
        "1. Выберите город вылета (например, Москва или MOW)\n"
        "2. Укажите город прилёта\n"
        "3. Введите дату вылета в формате <code>ГГГГ-ММ-ДД</code>\n"
        "4. Введите дату возврата или отправьте <code>-</code>, если только туда\n\n"

        "📊 <b>Сортировка результатов</b>\n"
        "После поиска нажмите:\n"
        "• 📉 <b>Дешевле</b> — чтобы отсортировать по возрастанию цены\n"
        "• 📈 <b>Дороже</b> — чтобы отсортировать по убыванию цены\n\n"

        "🌤 <b>Погода</b>\n"
        "Бот автоматически показывает погоду в городах вылета и прилёта.\n\n"

        "Если возникли проблемы — просто напишите /start и попробуйте снова!"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='HTML')


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