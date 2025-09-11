import sys
import os
import logging
import json
import tempfile
import asyncio
from datetime import datetime

# Добавляем путь к neuralex-main
neuralex_path = os.path.join(os.path.dirname(__file__), '..', 'neuralex-main')
if neuralex_path not in sys.path:
    sys.path.append(neuralex_path)

from telegram import Update
from telegram import Document, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .keyboards import main_menu, laws_menu, back_to_main_button, settings_menu, feedback_menu, rating_keyboard
from .analytics import BotAnalytics
from .user_manager import UserManager
from .rate_limiter import rate_limiter
from .redis_manager import RedisManager
from .state_manager import StateManager
from .admin_notifier import AdminNotifier
from .admin_handlers import AdminHandlers

# Настройка логирования для handlers
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные компоненты
law_assistant = None
analytics = None
user_manager = None
redis_manager = None
state_manager = None
admin_notifier = None
admin_handlers = None

def initialize_components():
    """Инициализирует все компоненты системы"""
    global law_assistant, analytics, user_manager, redis_manager, state_manager, admin_notifier, admin_handlers
    
    try:
        print("🔄 Инициализация компонентов бота...")
        
        from dotenv import load_dotenv
        load_dotenv()
        
        # Инициализация Redis менеджера
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        print(f"🔴 Подключение к Redis: {redis_url}")
        redis_manager = RedisManager(redis_url)
        redis_client = redis_manager.client
        
        # Инициализация менеджера состояний
        state_manager = StateManager(redis_client)
        print("✅ StateManager инициализирован")
        
        # Инициализация уведомлений администратора (будет инициализирован позже с bot instance)
        
        # Инициализация аналитики и менеджера пользователей
        analytics = BotAnalytics(redis_client)
        user_manager = UserManager(redis_client)
        print("✅ Analytics и UserManager инициализированы")
        
        # Инициализация админ-обработчиков
        admin_handlers = AdminHandlers(redis_client)
        print("✅ AdminHandlers инициализированы")
        
        # Инициализация neuralex компонентов
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
        
        print("🧠 Инициализация ИИ компонентов...")
        from neuralex_main.enhanced_neuralex import EnhancedNeuralex
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from langchain_community.vectorstores import Chroma
        import fitz  # PyMuPDF для работы с PDF
        import docx  # python-docx для работы с Word
        
        llm = ChatOpenAI(model='gpt-4o-mini', temperature=0.9, openai_api_key=openai_api_key)
        print("✅ LLM инициализирован")
        
        embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        print("✅ Embeddings инициализированы")
        
        vector_store = Chroma(persist_directory="chroma_db_legal_bot_part1", embedding_function=embeddings)
        print("✅ Vector store инициализирован")
        
        # Создаем экземпляр enhanced neuralex с поддержкой дополнительных документов
        law_assistant = EnhancedNeuralex(llm, embeddings, vector_store, redis_url, "documents")
        print("✅ Enhanced Neuralex инициализирован")
        
        # Выводим информацию о загруженных документах
        docs_info = law_assistant.get_documents_info()
        if docs_info['additional_documents_loaded']:
            stats = docs_info['stats']
            print(f"📚 Дополнительные документы: {stats['total_files']} файлов")
            for category, count in stats['categories'].items():
                if count > 0:
                    print(f"   • {category}: {count} файлов")
        else:
            print("📝 Дополнительные документы не найдены (используется базовая база)")
        
        logger.info("Все компоненты успешно инициализированы")
        print("🎉 Все компоненты успешно инициализированы!")
        return True
        
    except Exception as e:
        logger.error(f"Критическая ошибка инициализации: {e}")
        print(f"❌ Критическая ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()
        return False

# Инициализируем компоненты при импорте модуля
initialize_components()

def extract_text_from_file(file_path, file_extension):
    """Извлекает текст из различных типов файлов"""
    try:
        if file_extension.lower() == '.pdf':
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        
        elif file_extension.lower() in ['.docx', '.doc']:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        
        elif file_extension.lower() == '.txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        
        else:
            logging.warning(f"Неподдерживаемый формат файла: {file_extension}")
            return None
    except Exception as e:
        logging.error(f"Ошибка при извлечении текста: {e}")
        return None

async def analyze_document(document_text, user_id):
    """Анализирует документ на соответствие законодательству"""
    from prompts import DOCUMENT_ANALYSIS_PROMPT
    
    if law_assistant is None:
        return "❌ Сервис анализа документов временно недоступен."
    
    # Ограничиваем размер документа для анализа (4000 символов)
    truncated_text = document_text[:4000]
    if len(document_text) > 4000:
        truncated_text += "\n\n[Документ обрезан для анализа...]"
    
    # Используем промпт из prompts.py
    analysis_prompt = DOCUMENT_ANALYSIS_PROMPT.format(document_text=truncated_text)
    
    try:
        answer, _ = law_assistant.conversational(analysis_prompt, user_id)
        return answer
    except Exception as e:
        logging.error(f"Ошибка при анализе документа: {e}")
        return "❌ Произошла ошибка при анализе документа. Попробуйте позже."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    global admin_notifier, admin_handlers
    
    # Инициализируем admin_notifier если еще не инициализирован
    if admin_notifier is None:
        admin_notifier = AdminNotifier(context.bot)
    
    # Проверяем команду /admin
    if update.message.text == '/admin':
        if admin_handlers:
            await admin_handlers.admin_panel.handle_admin_command(update, context)
            return
        else:
            await update.message.reply_text("❌ Админ-панель недоступна")
            return
    
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name or "Пользователь"
    
    # Проверяем админ-команды
    if query.data.startswith('admin_') and admin_handlers:
        await admin_handlers.handle_admin_callback(query, user_id)
        return
    
    # Сбрасываем состояние пользователя при старте  
    if state_manager:
        state_manager.clear_user_state(user_id)
    
    # Логируем действие и обновляем активность
    if analytics:
        analytics.log_user_action(user_id, 'start', {'user_name': user_name})
    if user_manager:
        user_manager.update_last_activity(user_id)
    
    logging.info(f"Пользователь {user_name} (ID: {user_id}) запустил бота")
    
    welcome_text = f"""
👋 Добро пожаловать, {user_name}!

Я NEURALEX — ваш персональный ИИ-юрист 🤖⚖️

🎯 ЧТО Я УМЕЮ:
• Отвечаю на юридические вопросы простым языком
• Анализирую документы на соответствие закону
• Помогаю разобраться в правовых ситуациях
• Даю ссылки на конкретные статьи законов

📚 ЗНАЮ ВСЕ О:
Трудовом праве • Жилищных вопросах • Семейном праве
Налогах • ДТП и штрафах • Правах потребителей

💡 Начните с вопроса или выберите готовый пример ниже:
    """
    await update.message.reply_text(welcome_text, reply_markup=main_menu())

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик загруженных документов"""
    user_id = str(update.effective_user.id)
    
    # Проверяем состояние пользователя
    current_state = state_manager.get_user_state(user_id) if state_manager else None
    if current_state != 'checking_document':
        await update.message.reply_text(
            "Пожалуйста, сначала нажмите кнопку '📄 Проверить документ' в главном меню.",
            reply_markup=main_menu()
        )
        return
    
    document = update.message.document
    
    # Проверяем размер файла (максимум 20 МБ)
    if document.file_size > 20 * 1024 * 1024:
        await update.message.reply_text(
            "❌ Файл слишком большой. Максимальный размер: 20 МБ.",
            reply_markup=back_to_main_button()
        )
        if state_manager:
            state_manager.clear_user_state(user_id)
        return
    
    # Проверяем тип файла
    allowed_extensions = ['.pdf', '.docx', '.doc', '.txt']
    file_extension = os.path.splitext(document.file_name)[1].lower()
    
    if file_extension not in allowed_extensions:
        await update.message.reply_text(
            "❌ Неподдерживаемый формат файла.\n\n"
            "Поддерживаемые форматы: PDF, DOCX, DOC, TXT",
            reply_markup=back_to_main_button()
        )
        if state_manager:
            state_manager.clear_user_state(user_id)
        return
    
    # Показываем индикатор обработки
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # Отправляем промежуточное сообщение для анализа документа
    analyzing_message = await update.message.reply_text(
        "📄 **NEURALEX анализирует документ...**\n\n"
        "🔍 Извлекаю текст из файла\n"
        "⚖️ Проверяю соответствие законодательству\n"
        "📋 Готовлю детальный анализ\n"
        "⏳ Это займет несколько секунд",
        parse_mode='Markdown'
    )
    
    try:
        # Скачиваем файл
        file = await context.bot.get_file(document.file_id)
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            await file.download_to_drive(temp_file.name)
            temp_file_path = temp_file.name
        
        # Извлекаем текст из файла
        document_text = extract_text_from_file(temp_file_path, file_extension)
        
        # Удаляем временный файл
        os.unlink(temp_file_path)
        
        if not document_text or len(document_text.strip()) < 50:
            await update.message.reply_text(
                "❌ Не удалось извлечь текст из документа или документ слишком короткий.",
                reply_markup=back_to_main_button()
            )
            if state_manager:
                state_manager.clear_user_state(user_id)
            return
        
        logging.info(f"Анализ документа для пользователя {user_id}: {document.file_name}")
        
        # Анализируем документ
        analysis_result = await analyze_document(document_text, user_id)
        
        # Удаляем промежуточное сообщение
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=analyzing_message.message_id
            )
        except Exception as e:
            logging.warning(f"Не удалось удалить промежуточное сообщение анализа: {e}")
        
        # Форматируем ответ
        formatted_response = f"""📄 **Анализ документа:** {document.file_name}

📊 **Размер файла:** {document.file_size / 1024:.1f} КБ
📝 **Тип файла:** {file_extension.upper()}
📏 **Длина текста:** {len(document_text)} символов

⚖️ **Юридический анализ:**

{analysis_result}

⚠️ Данный анализ носит справочный характер. Для окончательного заключения обратитесь к квалифицированному юристу."""
        
        await update.message.reply_text(
            formatted_response,
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
        
        # Сбрасываем состояние пользователя
        if state_manager:
            state_manager.clear_user_state(user_id)
        
    except Exception as e:
        # Удаляем промежуточное сообщение при ошибке
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=analyzing_message.message_id
            )
        except Exception as delete_error:
            logging.warning(f"Не удалось удалить промежуточное сообщение при ошибке анализа: {e}")
        
        logging.error(f"Ошибка при обработке документа для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке документа. Попробуйте еще раз.",
            reply_markup=main_menu()
        )
        if state_manager:
            state_manager.clear_user_state(user_id)

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений пользователя"""
    user_id = str(update.effective_user.id)
    user_text = update.message.text
    
    current_state = state_manager.get_user_state(user_id) if state_manager else None
    
    # Проверяем состояние пользователя
    if current_state == 'asking_question':
        # Обрабатываем вопрос
        await process_legal_question(update, context, user_text, user_id)
    elif current_state == 'checking_document':
        await update.message.reply_text(
            "📄 Пожалуйста, загрузите документ для проверки.\n\n"
            "Поддерживаемые форматы: PDF, DOCX, DOC, TXT\n"
            "Максимальный размер: 20 МБ",
            reply_markup=back_to_main_button()
        )
    elif current_state == 'reporting_bug':
        # Обрабатываем сообщение об ошибке
        await process_bug_report(update, context, user_text, user_id)
    elif current_state == 'suggesting_improvement':
        # Обрабатываем предложение по улучшению
        await process_improvement_suggestion(update, context, user_text, user_id)
    else:
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки для навигации.",
            reply_markup=main_menu()
        )

async def process_legal_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str, user_id: str):
    """Обрабатывает юридический вопрос пользователя"""
    
    # Проверяем rate limit
    if not rate_limiter.is_allowed(user_id):
        remaining_time = rate_limiter.get_reset_time(user_id)
        await update.message.reply_text(
            f"⏰ **Превышен лимит запросов**\n\n"
            f"Попробуйте снова через {int(remaining_time)} секунд.\n"
            f"Это ограничение помогает обеспечить стабильную работу бота для всех пользователей.",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
        if state_manager:
            state_manager.clear_user_state(user_id)
        return
    
    # Логируем вопрос
    if analytics:
        analytics.log_user_action(user_id, 'ask_question', {'question_length': len(user_text)})
    
    if law_assistant is None:
        await update.message.reply_text(
            "❌ Извините, сервис ИИ-консультаций временно недоступен.\n\n"
            "Возможные причины:\n"
            "• Проблемы с подключением к OpenAI API\n"
            "• Неверный API ключ\n"
            "• Превышен лимит запросов OpenAI\n\n"
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode='Markdown',
            reply_markup=main_menu()
        )
        if state_manager:
            state_manager.clear_user_state(user_id)
        return
    
    # Показываем индикатор печати
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # Отправляем промежуточное сообщение
    thinking_message = await update.message.reply_text(
        "🤖 **NEURALEX анализирует ваш вопрос...**\n\n"
        "⚡ Ищу релевантную информацию в базе законов\n"
        "🧠 Готовлю развернутый ответ\n"
        "⏳ Это займет несколько секунд",
        parse_mode='Markdown'
    )
    
    logging.info(f"Обработка вопроса от пользователя {user_id}: {user_text[:100]}...")
    
    try:
        # Получаем ответ от ИИ-юриста
        answer, _ = law_assistant.conversational(user_text, user_id)
        
        # Форматируем ответ
        formatted_answer = f"🤖 **NEURALEX | Юридическая консультация**\n\n{answer}\n\n"
        formatted_answer += "⚠️ Информация носит справочный характер. При серьезных вопросах обратитесь к юристу.\n\n"
        formatted_answer += "💡 Был ли ответ полезен? Оцените его ниже!"
        
        # Сохраняем ответ для возможной оценки
        if state_manager:
            state_manager.save_last_answer(user_id, user_text, answer)
        
        # Удаляем промежуточное сообщение
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=thinking_message.message_id
            )
        except Exception as e:
            logging.warning(f"Не удалось удалить промежуточное сообщение: {e}")
        
        # Добавляем кнопку оценки
        keyboard = [
            [InlineKeyboardButton("⭐ Оценить ответ", callback_data='rate_last_answer'),
             InlineKeyboardButton("❓ Задать еще вопрос", callback_data='ask')],
            [InlineKeyboardButton("🔙 Главное меню", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            formatted_answer,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        logging.info(f"Успешно обработан вопрос пользователя {user_id}")
        
        # Сбрасываем состояние пользователя
        if state_manager:
            state_manager.clear_user_state(user_id)
        
    except Exception as openai_error:
        # Удаляем промежуточное сообщение при ошибке
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=thinking_message.message_id
            )
        except Exception as delete_error:
            logging.warning(f"Не удалось удалить промежуточное сообщение при ошибке: {e}")
        
        # Специальная обработка ошибок OpenAI
        error_message = str(openai_error).lower()
        logging.error(f"Ошибка при обработке запроса пользователя {user_id}: {openai_error}")
        
        if "rate limit" in error_message or "quota" in error_message:
            await update.message.reply_text(
                "⏰ **Превышен лимит запросов к OpenAI**\n\n"
                "Слишком много запросов в данный момент. "
                "Попробуйте через несколько минут.",
                parse_mode='Markdown',
                reply_markup=main_menu()
            )
        elif "api key" in error_message or "authentication" in error_message:
            await update.message.reply_text(
                "🔑 **Проблема с аутентификацией**\n\n"
                "Проблемы с API ключом OpenAI. "
                "Обратитесь к администратору.",
                parse_mode='Markdown',
                reply_markup=main_menu()
            )
        elif "insufficient_quota" in error_message:
            await update.message.reply_text(
                "💳 **Исчерпан лимит OpenAI**\n\n"
                "Закончились кредиты на аккаунте OpenAI.\n\n"
                "Проверьте баланс на https://platform.openai.com/account/billing\n"
                "Если баланс пополнен, попробуйте через несколько минут.",
                parse_mode='Markdown',
                reply_markup=main_menu()
            )
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке вашего запроса.\n\n"
                f"Детали: {str(openai_error)[:100]}...\n\n"
                "Попробуйте еще раз через несколько минут.",
                parse_mode='Markdown',
                reply_markup=main_menu()
            )
        
        if state_manager:
            state_manager.clear_user_state(user_id)
        
    except Exception as e:
        # Удаляем промежуточное сообщение при ошибке
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=thinking_message.message_id
            )
        except Exception as delete_error:
            logging.warning(f"Не удалось удалить промежуточное сообщение при ошибке: {e}")
        
        logging.error(f"Ошибка при обработке запроса пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке вашего запроса. Попробуйте еще раз.",
            reply_markup=main_menu()
    elif query.data == 'check_document':
        if state_manager:
            state_manager.set_user_state(user_id, 'checking_document')
        if analytics:
            analytics.log_user_action(user_id, 'click_check_document')
        await query.edit_message_text(
            "📄 **Проверка документов**\n\n"
            "Загрузите документ для анализа на соответствие российскому законодательству.\n\n"
            "📋 **Что я проверю:**\n"
            "• Соответствие формальным требованиям\n"
            "• Наличие обязательных реквизитов\n"
            "• Соответствие действующему законодательству\n"
            "• Выявление нарушений и несоответствий\n"
            "• Рекомендации по исправлению\n\n"
            "📎 **Поддерживаемые форматы:**\n"
            "• PDF (.pdf)\n"
            "• Microsoft Word (.docx, .doc)\n"
            "• Текстовые файлы (.txt)\n\n"
            "📏 **Ограничения:**\n"
            "• Максимальный размер: 20 МБ\n"
            "• Документ должен содержать читаемый текст\n\n"
            "Прикрепите файл к следующему сообщению:",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'laws':
        if analytics:
            analytics.log_user_action(user_id, 'click_laws')
        await query.edit_message_text(
            "📚 **Доступные категории законов:**\n\n"
            "Выберите интересующую вас область права для получения общей информации:",
            parse_mode='Markdown',
            reply_markup=laws_menu()
        )
    
    elif query.data == 'clear_history':
        if analytics:
            analytics.log_user_action(user_id, 'clear_history')
        # Очищаем историю пользователя
        if law_assistant:
            try:
                # Очищаем историю в Redis
                chat_history = law_assistant.get_session_history(user_id)
                chat_history.clear()
                await query.edit_message_text(
                    "🔄 **История чата очищена**\n\n"
                    "Ваша история общения с ботом была успешно удалена. "
                    "Теперь я не буду помнить предыдущие вопросы и ответы.",
                    parse_mode='Markdown',
                    reply_markup=back_to_main_button()
                )
                logging.info(f"История чата очищена для пользователя {user_id}")
            except Exception as e:
                logging.error(f"Ошибка при очистке истории для пользователя {user_id}: {e}")
                await query.edit_message_text(
                    "❌ Произошла ошибка при очистке истории.",
                    reply_markup=back_to_main_button()
                )
        else:
            await query.edit_message_text(
                "❌ Сервис временно недоступен.",
                reply_markup=back_to_main_button()
            )
    
    elif query.data.startswith('law_'):
        if analytics:
            analytics.log_user_action(user_id, 'view_law', {'law': query.data})
        law_info = get_law_info(query.data)
        await query.edit_message_text(
            law_info,
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'back_to_main':
        if state_manager:
            state_manager.clear_user_state(user_id)  # Сбрасываем состояние
        await query.edit_message_text(
            f"👋 С возвращением, {user_name}!\n\nВыберите действие:",
            reply_markup=main_menu()
        )
    
    elif query.data == 'settings':
        if analytics:
            analytics.log_user_action(user_id, 'click_settings')
        await show_settings(query, user_id)
    
    elif query.data == 'settings_notifications':
        if analytics:
            analytics.log_user_action(user_id, 'toggle_notifications')
        await toggle_notifications(query, user_id)
    
    elif query.data == 'settings_language':
        if analytics:
            analytics.log_user_action(user_id, 'change_language')
        await query.edit_message_text(
            "🌐 **Выбор языка**\n\n"
            "В данный момент поддерживается только русский язык.\n"
            "Поддержка других языков будет добавлена в будущих версиях.",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'feedback':
        if analytics:
            analytics.log_user_action(user_id, 'click_feedback')
        await query.edit_message_text(
            "💬 **Обратная связь**\n\n"
            "Ваше мнение важно для нас! Помогите улучшить бота:",
            parse_mode='Markdown',
            reply_markup=feedback_menu()
        )
    
    elif query.data == 'report_bug':
        if state_manager:
            state_manager.set_user_state(user_id, 'reporting_bug')
        await query.edit_message_text(
            "🐛 **Сообщить об ошибке**\n\n"
            "Опишите проблему, с которой вы столкнулись:\n"
            "• Что вы делали?\n"
            "• Что произошло?\n"
            "• Что ожидали увидеть?\n\n"
            "Напишите ваше сообщение в следующем сообщении:",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'suggest_improvement':
        if state_manager:
            state_manager.set_user_state(user_id, 'suggesting_improvement')
        await query.edit_message_text(
            "💡 **Предложить улучшение**\n\n"
            "Поделитесь своими идеями по улучшению бота:\n"
            "• Какие функции хотели бы добавить?\n"
            "• Что можно улучшить?\n"
            "• Какие проблемы заметили?\n\n"
            "Напишите ваше предложение в следующем сообщении:",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'rate_last_answer':
        last_answer = state_manager.get_last_answer(user_id) if state_manager else None
        if last_answer:
            await query.edit_message_text(
                "⭐ **Оцените качество ответа**\n\n"
                "Насколько полезным был последний ответ?",
                parse_mode='Markdown',
                reply_markup=rating_keyboard()
            )
        else:
            await query.edit_message_text(
                "❌ Нет ответа для оценки",
                reply_markup=back_to_main_button()
            )
    
    elif query.data.startswith('rate_'):
        rating = int(query.data.split('_')[1])
        last_answer = state_manager.get_last_answer(user_id) if state_manager else None
        if last_answer and analytics:
            analytics.log_question_rating(user_id, last_answer['question'], rating)
            analytics.log_user_action(user_id, 'rate_answer', {'rating': rating})
            
            # Отправляем уведомление о низкой оценке
            if admin_notifier and rating <= 2:
                user_name = update.effective_user.first_name or "Пользователь"
                await admin_notifier.send_low_rating_alert(
                    user_id, user_name, rating, last_answer['question']
                )
            
            await query.edit_message_text(
                f"⏰ Превышен лимит запросов\n\n"
                f"Вы поставили {rating} {'⭐' * rating}\n\n"
                f"Это ограничение помогает обеспечить стабильную работу бота для всех пользователей.",
                reply_markup=back_to_main_button()
            )
            
            # Удаляем оцененный ответ
            if state_manager:
                state_manager.clear_last_answer(user_id)
        else:
            await query.edit_message_text(
                "❌ Ошибка при сохранении оценки",
                reply_markup=back_to_main_button()
            )
    
    elif query.data == 'settings_stats':
        await show_user_stats(query, user_id)
    
    elif query.data == 'export_history':
        await export_user_history(query, user_id)
    
    elif query.data == 'documents_status':
        await show_documents_status(query, user_id)
    
    elif query.data == 'reload_documents':
        await reload_documents(query, user_id)
    
    else:
        logging.warning(f"Неизвестная команда кнопки: {query.data} от пользователя {user_id}")

def get_law_info(law_code):
    """Возвращает информацию о выбранном законе"""
    law_descriptions = {
        'law_constitution': """
⚖️ **Конституция Российской Федерации**

📅 Принята: 12 декабря 1993 года
📋 Статус: Основной закон государства

🎯 **Основные разделы:**
• Основы конституционного строя
• Права и свободы человека и гражданина
• Федеративное устройство
• Президент РФ, Федеральное Собрание, Правительство
• Судебная власть и прокуратура
• Местное самоуправление

💡 *Конституция имеет высшую юридическую силу и прямое действие на всей территории РФ.*
        """,
        
        'law_civil': """
🏛️ **Гражданский кодекс РФ**

📅 Действует с: 1995 года (с изменениями)
📋 Структура: 4 части

🎯 **Основные разделы:**
• Общие положения (лица, сделки, представительство)
• Право собственности и другие вещные права
• Обязательственное право (договоры, деликты)
• Отдельные виды обязательств
• Наследственное право
• Международное частное право

💡 *Регулирует имущественные и связанные с ними личные неимущественные отношения.*
        """,
        
        'law_criminal': """
⚔️ **Уголовный кодекс РФ**

📅 Действует с: 1 января 1997 года
📋 Структура: Общая и Особенная части

🎯 **Основные разделы:**
• Преступление и наказание
• Назначение наказания
• Освобождение от уголовной ответственности
• Преступления против личности
• Преступления в сфере экономики
• Преступления против общественной безопасности
• Преступления против государственной власти

💡 *Определяет, какие деяния являются преступлениями и какие наказания за них предусмотрены.*
        """,
        
        'law_labor': """
💼 **Трудовой кодекс РФ**

📅 Действует с: 1 февраля 2002 года
📋 Структура: 6 частей, 14 разделов

🎯 **Основные разделы:**
• Трудовые отношения и трудовой договор
• Рабочее время и время отдыха
• Оплата и нормирование труда
• Гарантии и компенсации
• Дисциплина труда
• Охрана труда
• Материальная ответственность
• Трудовые споры

💡 *Регулирует трудовые отношения между работниками и работодателями.*
        """,
        
        'law_family': """
👨‍👩‍👧‍👦 **Семейный кодекс РФ**

📅 Действует с: 1 марта 1996 года
📋 Структура: 8 разделов

🎯 **Основные разделы:**
• Заключение и прекращение брака
• Права и обязанности супругов
• Права и обязанности родителей и детей
• Алиментные обязательства
• Формы воспитания детей, оставшихся без попечения родителей
• Применение семейного законодательства к семейным отношениям с участием иностранных граждан

💡 *Регулирует семейные отношения: брак, родительство, опека, усыновление.*
        """,
        
        'law_tax': """
💰 **Налоговый кодекс РФ**

📅 Действует с: 1999 года (1 часть), 2001 года (2 часть)
📋 Структура: 2 части

🎯 **Основные разделы:**
**Часть 1:** Общие принципы налогообложения
• Система налогов и сборов
• Налогоплательщики и налоговые агенты
• Налоговые органы
• Налоговые правонарушения и ответственность

**Часть 2:** Конкретные налоги
• НДС, налог на прибыль, НДФЛ
• Акцизы, налог на имущество
• Транспортный и земельный налоги

💡 *Устанавливает систему налогов и сборов в РФ.*
        """,
        
        'law_housing': """
🏠 **Жилищный кодекс РФ**

📅 Действует с: 1 марта 2005 года
📋 Структура: 8 разделов

🎯 **Основные разделы:**
• Общие положения жилищного законодательства
• Право собственности и другие вещные права на жилые помещения
• Жилые помещения социального использования
• Специализированный жилищный фонд
• Жилищные и жилищно-строительные кооперативы
• Товарищества собственников жилья
• Плата за жилое помещение и коммунальные услуги
• Управление многоквартирными домами

💡 *Регулирует жилищные отношения, права и обязанности собственников и нанимателей жилья.*
        """
    }
    
    return law_descriptions.get(law_code, "Информация о данном законе временно недоступна.")

async def show_settings(query, user_id: str):
    """Показывает настройки пользователя"""
    if user_manager:
        settings = user_manager.get_user_settings(user_id)
        notifications_status = "🔔 Включены" if settings.get('notifications', True) else "🔕 Выключены"
        language = settings.get('language', 'ru')
        
        settings_text = f"""
⚙️ **Настройки**

🔔 **Уведомления:** {notifications_status}
🌐 **Язык:** {language.upper()}
📅 **Дата регистрации:** {settings.get('created_at', 'Неизвестно')[:10]}
⏰ **Последняя активность:** {settings.get('last_active', 'Неизвестно')[:10]}
        """
    else:
        settings_text = "⚙️ **Настройки**\n\nНастройки временно недоступны."
    
    await query.edit_message_text(
        settings_text,
        parse_mode='Markdown',
        reply_markup=settings_menu()
    )

async def show_user_stats(query, user_id: str):
    """Показывает статистику пользователя"""
    if analytics:
        stats = analytics.get_user_stats(user_id)
        avg_rating = analytics.get_average_rating()
        
        stats_text = f"""
📊 **Ваша статистика**

❓ **Задано вопросов:** {stats.get('ask_question', 0)}
📄 **Проверено документов:** {stats.get('check_document', 0)}
📚 **Просмотрено законов:** {stats.get('view_law', 0)}
🔄 **Всего действий:** {stats.get('total_actions', 0)}

⭐ **Средний рейтинг бота:** {avg_rating:.1f}/5.0
        """
    else:
        stats_text = "📊 **Статистика**\n\nСтатистика временно недоступна."
    
    await query.edit_message_text(
        stats_text,
        parse_mode='Markdown',
        reply_markup=back_to_main_button()
    )

async def export_user_history(query, user_id: str):
    """Экспортирует историю пользователя"""
    if user_manager:
        history_json = user_manager.export_user_history(user_id)
        if history_json:
            # Создаем временный файл
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                f.write(history_json)
                temp_path = f.name
            
            try:
                # Отправляем файл
                with open(temp_path, 'rb') as f:
                    await query.message.reply_document(
                        document=f,
                        filename=f"neuralex_history_{user_id}_{datetime.now().strftime('%Y%m%d')}.json",
                        caption="📝 **Экспорт истории**\n\nВаша история чатов с ботом в формате JSON."
                    )
                
                await query.edit_message_text(
                    "✅ **История экспортирована**\n\n"
                    "Файл с вашей историей отправлен выше.",
                    parse_mode='Markdown',
                    reply_markup=back_to_main_button()
                )
                
                # Удаляем временный файл
                os.unlink(temp_path)
                
            except Exception as e:
                logger.error(f"Ошибка при отправке файла истории: {e}")
                await query.edit_message_text(
                    "❌ Ошибка при экспорте истории",
                    reply_markup=back_to_main_button()
                )
        else:
            await query.edit_message_text(
                "❌ Не удалось экспортировать историю",
                reply_markup=back_to_main_button()
            )
    else:
        await query.edit_message_text(
            "❌ Экспорт истории временно недоступен",
            reply_markup=back_to_main_button()
        )

async def show_documents_status(query, user_id: str):
    """Показывает статус загруженных документов"""
    if law_assistant:
        docs_info = law_assistant.get_documents_info()
        stats = docs_info.get('stats', {})
        
        status_text = "📚 **Статус документов**\n\n"
        
        if docs_info['additional_documents_loaded']:
            status_text += f"✅ **Дополнительные документы:** Загружены\n"
            status_text += f"📊 **Всего файлов:** {stats.get('total_files', 0)}\n\n"
            
            categories_names = {
                'laws': '⚖️ Федеральные законы',
                'codes': '📖 Кодексы РФ',
                'articles': '📝 Юридические статьи', 
                'court_practice': '🏛️ Судебная практика'
            }
            
            for category, count in stats.get('categories', {}).items():
                name = categories_names.get(category, category)
                status_text += f"{name}: **{count}** файлов\n"
            
            status_text += f"\n📋 **Поддерживаемые форматы:**\n"
            formats = stats.get('supported_formats', [])
            status_text += ", ".join(formats)
            
        else:
            status_text += "📝 **Дополнительные документы:** Не найдены\n"
            status_text += "💡 Добавьте файлы в папку `documents/` для расширения базы знаний\n\n"
            status_text += "**Структура папок:**\n"
            status_text += "• `documents/laws/` - Федеральные законы\n"
            status_text += "• `documents/codes/` - Кодексы РФ\n"
            status_text += "• `documents/articles/` - Юридические статьи\n"
            status_text += "• `documents/court_practice/` - Судебная практика"
        
        if docs_info['base_vector_store_available']:
            status_text += "\n\n✅ **Базовая векторная база:** Доступна"
        else:
            status_text += "\n\n❌ **Базовая векторная база:** Недоступна"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Перезагрузить документы", callback_data='reload_documents')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            status_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await query.edit_message_text(
            "❌ Информация о документах недоступна",
            reply_markup=back_to_main_button()
        )

async def reload_documents(query, user_id: str):
    """Перезагружает дополнительные документы"""
    if law_assistant and hasattr(law_assistant, 'reload_documents'):
        # Показываем индикатор загрузки
        await query.edit_message_text(
            "🔄 **Перезагрузка документов...**\n\n"
            "📚 Сканирую папку documents/\n"
            "🔍 Ищу новые файлы\n"
            "⚡ Обновляю векторную базу\n"
            "⏳ Это может занять несколько секунд",
            parse_mode='Markdown'
        )
        
        try:
            success = law_assistant.reload_documents()
            
            if success:
                docs_info = law_assistant.get_documents_info()
                stats = docs_info.get('stats', {})
                
                result_text = "✅ **Документы успешно перезагружены!**\n\n"
                result_text += f"📊 **Всего файлов:** {stats.get('total_files', 0)}\n\n"
                
                categories_names = {
                    'laws': '⚖️ Федеральные законы',
                    'codes': '📖 Кодексы РФ', 
                    'articles': '📝 Юридические статьи',
                    'court_practice': '🏛️ Судебная практика'
                }
                
                for category, count in stats.get('categories', {}).items():
                    if count > 0:
                        name = categories_names.get(category, category)
                        result_text += f"{name}: **{count}** файлов\n"
                
                if analytics:
                    analytics.log_user_action(user_id, 'reload_documents')
                
            else:
                result_text = "❌ **Ошибка при перезагрузке документов**\n\n"
                result_text += "Проверьте логи для получения подробной информации."
            
            await query.edit_message_text(
                result_text,
                parse_mode='Markdown',
                reply_markup=back_to_main_button()
            )
            
        except Exception as e:
            logger.error(f"Ошибка при перезагрузке документов: {e}")
            await query.edit_message_text(
                "❌ **Произошла ошибка при перезагрузке документов**\n\n"
                "Попробуйте еще раз или обратитесь к администратору.",
                parse_mode='Markdown',
                reply_markup=back_to_main_button()
            )
    else:
        await query.edit_message_text(
            "❌ Функция перезагрузки документов недоступна",
            reply_markup=back_to_main_button()
        )

async def toggle_notifications(query, user_id: str):
    """Переключает настройки уведомлений"""
    if user_manager:
        settings = user_manager.get_user_settings(user_id)
        current_status = settings.get('notifications', True)
        new_status = not current_status
        
        settings['notifications'] = new_status
        user_manager.save_user_settings(user_id, settings)
        
        status_text = "включены" if new_status else "выключены"
        await query.edit_message_text(
            f"🔔 **Уведомления {status_text}**\n\n"
            f"Настройка сохранена.",
            parse_mode='Markdown',
            reply_markup=settings_menu()
        )
    else:
        await query.edit_message_text(
            "❌ Настройки временно недоступны",
            reply_markup=back_to_main_button()
        )

async def process_bug_report(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str, user_id: str):
    """Обрабатывает сообщение об ошибке"""
    if analytics:
        analytics.log_user_action(user_id, 'bug_report', {'report_length': len(user_text)})
    
    # Сохраняем отчет об ошибке
    if user_manager and user_manager.redis_client:
        try:
            import json
            bug_report = {
                'user_id': user_id,
                'report': user_text,
                'timestamp': datetime.now().isoformat(),
                'type': 'bug_report'
            }
            key = f"feedback:bug:{user_id}:{datetime.now().timestamp()}"
            user_manager.redis_client.setex(key, 7 * 24 * 3600, json.dumps(bug_report))  # 7 дней
            
            # Отправляем уведомление администратору
            if admin_notifier:
                user_name = update.effective_user.first_name or "Пользователь"
                await admin_notifier.send_bug_report(user_id, user_name, user_text)
                
        except Exception as e:
            logger.error(f"Ошибка при сохранении отчета об ошибке: {e}")
    
    await update.message.reply_text(
        "✅ **Спасибо за отчет об ошибке!**\n\n"
        "Ваше сообщение получено и будет рассмотрено разработчиками. "
        "Мы работаем над улучшением бота и ценим вашу помощь!",
        parse_mode='Markdown',
        reply_markup=main_menu()
    )
    
    if state_manager:
        state_manager.clear_user_state(user_id)
    
    logger.info(f"Получен отчет об ошибке от пользователя {user_id}: {user_text[:100]}...")

async def process_improvement_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str, user_id: str):
    """Обрабатывает предложение по улучшению"""
    if analytics:
        analytics.log_user_action(user_id, 'improvement_suggestion', {'suggestion_length': len(user_text)})
    
    # Сохраняем предложение
    if user_manager and user_manager.redis_client:
        try:
            import json
            suggestion = {
                'user_id': user_id,
                'suggestion': user_text,
                'timestamp': datetime.now().isoformat(),
                'type': 'improvement_suggestion'
            }
            key = f"feedback:suggestion:{user_id}:{datetime.now().timestamp()}"
            user_manager.redis_client.setex(key, 7 * 24 * 3600, json.dumps(suggestion))  # 7 дней
            
            # Отправляем уведомление администратору
            if admin_notifier:
                user_name = update.effective_user.first_name or "Пользователь"
                await admin_notifier.send_improvement_suggestion(user_id, user_name, user_text)
                
        except Exception as e:
            logger.error(f"Ошибка при сохранении предложения: {e}")
    
    await update.message.reply_text(
        "💡 **Спасибо за предложение!**\n\n"
        "Ваша идея получена и будет рассмотрена командой разработки. "
        "Лучшие предложения будут реализованы в будущих версиях бота!",
        parse_mode='Markdown',
        reply_markup=main_menu()
    )
    
    if state_manager:
        state_manager.clear_user_state(user_id)
    
    logger.info(f"Получено предложение от пользователя {user_id}: {user_text[:100]}...")