from telebot.types import ReplyKeyboardMarkup

def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("Поиск авиабилетов", "🌤 Погода", "📚 История", "🗑 Очистить историю")
    return markup