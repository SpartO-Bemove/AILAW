from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    keyboard = [
        [InlineKeyboardButton("Задать вопрос", callback_data='ask')],
        [InlineKeyboardButton("Посмотреть законы", callback_data='laws')],
    ]
    return InlineKeyboardMarkup(keyboard)
