import sys
import os

# Добавляем путь к neuralex-main в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'neuralex-main'))

from telegram import Update
from telegram.ext import ContextTypes

from .keyboards import main_menu

try:
    from neuralex_main import neuralex
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain_community.vectorstores import Chroma
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Инициализация компонентов neuralex
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
    
    llm = ChatOpenAI(model='gpt-4o-mini', temperature=0.9, openai_api_key=openai_api_key)
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    vector_store = Chroma(persist_directory="chroma_db_legal_bot_part1", embedding_function=embeddings)
    
    # Создаем экземпляр neuralex
    law_assistant = neuralex(llm, embeddings, vector_store)
    
except ImportError as e:
    print(f"Ошибка импорта neuralex: {e}")
    law_assistant = None

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = str(update.effective_user.id)
    
    if law_assistant is None:
        await update.message.reply_text("Извините, сервис временно недоступен. Попробуйте позже.")
        return
    
    try:
        # Используем user_id как session_id для персонализации
        answer, _ = law_assistant.conversational(user_text, user_id)
        await update.message.reply_text(answer)
    except Exception as e:
        print(f"Ошибка при обработке запроса: {e}")
        await update.message.reply_text("Произошла ошибка при обработке вашего запроса. Попробуйте еще раз.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я ваш юрист-бот. Выберите действие:",
        reply_markup=main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'ask':
        await query.edit_message_text("Напишите свой вопрос:")
    elif query.data == 'laws':
