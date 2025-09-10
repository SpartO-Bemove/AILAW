from telegram import Update
from telegram.ext import CallbackContext

from .keyboards import main_menu
from neuralex_main.app import get_answer_from_model

def handle_user_message(update: Update, context):
    user_text = update.message.text
    answer = get_answer_from_model(user_text)  # твоя функция, которая ищет в Chroma
    update.message.reply_text(answer)


def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Привет! Я ваш юрист-бот. Выберите действие:",
        reply_markup=main_menu()
    )

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    if query.data == 'ask':
        query.edit_message_text("Напишите свой вопрос:")
    elif query.data == 'laws':
        query.edit_message_text("Список законов:")
