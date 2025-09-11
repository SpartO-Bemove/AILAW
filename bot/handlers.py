import sys
import os
import logging
import asyncio
import json
from datetime import datetime
from typing import Optional

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError

# Document processing imports
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logging.warning("PyMuPDF не установлен - PDF файлы не будут обрабатываться")

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logging.warning("python-docx не установлен - DOCX файлы не будут обрабатываться")

# Local imports
from .config import OPENAI_API_KEY, MAX_FILE_SIZE, ALLOWED_EXTENSIONS, CHROMA_DB_PATH, REDIS_URL
from .keyboards import main_menu, laws_menu, back_to_main_button, settings_menu, feedback_menu, rating_keyboard
from .analytics import BotAnalytics
from .user_manager import UserManager
from .state_manager import StateManager
from .rate_limiter import rate_limiter
from .redis_manager import RedisManager
from .admin_handlers import AdminHandlers

# Инициализация компонентов
logger = logging.getLogger(__name__)

# Глобальные переменные
law_assistant = None
analytics = None
user_manager = None
state_manager = None
admin_handlers = None
admin_notifier = None

def initialize_components():
    """Инициализирует все компоненты системы"""
    global law_assistant, analytics, user_manager, state_manager, admin_handlers, admin_notifier
    
    try:
        logger.info("🔄 Инициализация компонентов...")
        
        # Инициализируем Redis
        redis_manager = RedisManager(REDIS_URL)
        redis_client = redis_manager.client
        
        if redis_client:
            logger.info("✅ Redis подключен")
        else:
            logger.warning("⚠️ Redis недоступен - работаем без кэширования")
        
        # Инициализируем аналитику
        analytics = BotAnalytics(redis_client)
        logger.info("✅ Аналитика инициализирована")
        
        # Инициализируем менеджер пользователей
        user_manager = UserManager(redis_client)
        logger.info("✅ Менеджер пользователей инициализирован")
        
        # Инициализируем менеджер состояний
        state_manager = StateManager(redis_client)
        logger.info("✅ Менеджер состояний инициализирован")
        
        # Инициализируем админ-обработчики
        admin_handlers = AdminHandlers(redis_client)
        logger.info("✅ Админ-обработчики инициализированы")
        
        # Инициализируем neuralex
        try:
            # Добавляем путь к neuralex-main
            neuralex_path = os.path.join(os.path.dirname(__file__), '..', 'neuralex-main')
            if neuralex_path not in sys.path:
                sys.path.append(neuralex_path)
            
            from langchain_openai import ChatOpenAI, OpenAIEmbeddings
            from langchain_community.vectorstores import Chroma
            
            # Проверяем наличие векторной базы
            if os.path.exists(CHROMA_DB_PATH):
                logger.info("✅ Векторная база данных найдена")
                
                # Инициализируем компоненты
                llm = ChatOpenAI(model='gpt-4o-mini', temperature=0.9, openai_api_key=OPENAI_API_KEY)
                embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
                vector_store = Chroma(persist_directory=CHROMA_DB_PATH, embedding_function=embeddings)
                
                # Пробуем импортировать enhanced_neuralex, если не получается - используем базовый
                try:
                    from enhanced_neuralex import EnhancedNeuralex
                    law_assistant = EnhancedNeuralex(llm, embeddings, vector_store, REDIS_URL)
                    logger.info("✅ Enhanced Neuralex инициализирован")
                except ImportError:
                    logger.warning("Enhanced Neuralex недоступен, используем базовый")
                    from neuralex_main import neuralex
                    law_assistant = neuralex(llm, embeddings, vector_store, REDIS_URL)
                    logger.info("✅ Базовый Neuralex инициализирован")
                
            else:
                logger.error(f"❌ Векторная база данных не найдена: {CHROMA_DB_PATH}")
                law_assistant = None
                
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации neuralex: {e}")
            law_assistant = None
        
        # Инициализируем уведомления администратора
        try:
            from .admin_notifier import AdminNotifier
            from telegram import Bot
            bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
            admin_notifier = AdminNotifier(bot)
            logger.info("✅ Уведомления администратора инициализированы")
        except Exception as e:
            logger.warning(f"⚠️ Уведомления администратора недоступны: {e}")
            admin_notifier = None
        
        logger.info("🎉 Все компоненты инициализированы успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка инициализации: {e}")
        return False

# Инициализируем компоненты при импорте модуля
initialize_components()

def extract_text_from_file(file_path: str, file_extension: str) -> Optional[str]:
    """Извлекает текст из файла в зависимости от его типа"""
    try:
        if file_extension == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        elif file_extension == '.pdf' and PYMUPDF_AVAILABLE:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        
        elif file_extension in ['.docx', '.doc'] and DOCX_AVAILABLE:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        
        else:
            logger.warning(f"Неподдерживаемый формат файла: {file_extension}")
            return None
            
    except Exception as e:
        logger.error(f"Ошибка при извлечении текста из файла: {e}")
        return None

def analyze_document(document_text: str) -> str:
    """Анализирует документ с помощью ИИ"""
    if not law_assistant:
        return "❌ ИИ-анализатор временно недоступен. Попробуйте позже."
    
    try:
        # Импортируем промпт для анализа документов
        try:
            from prompts import DOCUMENT_ANALYSIS_PROMPT
        except ImportError:
            # Fallback промпт если файл недоступен
            DOCUMENT_ANALYSIS_PROMPT = """
            Проанализируй следующий документ на соответствие российскому законодательству:
            
            {document_text}
            
            Дай краткое заключение о юридической корректности документа.
            """
        
        # Формируем промпт для анализа
        analysis_prompt = DOCUMENT_ANALYSIS_PROMPT.format(document_text=document_text[:3000])
        
        # Получаем анализ от ИИ
        analysis, _ = law_assistant.conversational(analysis_prompt, "document_analysis")
        
        return analysis
        
    except Exception as e:
        logger.error(f"Ошибка при анализе документа: {e}")
        return "❌ Произошла ошибка при анализе документа. Попробуйте позже."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = str(user.id)
    
    # Логируем действие
    if analytics:
        analytics.log_user_action(user_id, 'start')
    
    # Обновляем активность пользователя
    if user_manager:
        user_manager.update_last_activity(user_id)
    
    # Проверяем админ-команду
    if update.message.text == '/admin':
        if admin_handlers and admin_handlers.admin_panel.is_admin(user_id):
            await admin_handlers.admin_panel.handle_admin_command(update, context)
            return
        else:
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return
    
    # Обычное приветствие
    welcome_message = f"""
🤖 **Добро пожаловать в Neuralex!**

Привет, {user.first_name}! Я ваш ИИ-юрист, готовый помочь с вопросами российского права.

🎯 **Что я умею:**
• ❓ Отвечать на юридические вопросы
• 📄 Анализировать документы на соответствие законам
• 📚 Предоставлять информацию о кодексах РФ
• ⚖️ Помогать разбираться в правовых ситуациях

💡 **Выберите действие:**
    """
    
    await update.message.reply_text(
        welcome_message,
        parse_mode='Markdown',
        reply_markup=main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    await query.answer()
    
    # Проверяем админ-команды
    if admin_handlers and query.data.startswith('admin_'):
        await admin_handlers.handle_admin_callback(query, user_id)
        return
    
    # Обновляем активность пользователя
    if user_manager:
        user_manager.update_last_activity(user_id)
    
    # Основные кнопки
    if query.data == 'ask':
        if analytics:
            analytics.log_user_action(user_id, 'ask_question')
        
        if state_manager:
            state_manager.set_user_state(user_id, 'waiting_for_question')
        
        await query.edit_message_text(
            "❓ **Задайте ваш юридический вопрос**\n\n"
            "Опишите вашу ситуацию максимально подробно. "
            "Чем больше деталей вы предоставите, тем точнее будет ответ.\n\n"
            "💡 **Примеры вопросов:**\n"
            "• Какие права у работника при увольнении?\n"
            "• Как оформить развод через ЗАГС?\n"
            "• Какая ответственность за нарушение ПДД?\n\n"
            "✍️ Напишите ваш вопрос следующим сообщением:",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'check_document':
        if analytics:
            analytics.log_user_action(user_id, 'check_document')
        
        if state_manager:
            state_manager.set_user_state(user_id, 'waiting_for_document')
        
        await query.edit_message_text(
            "📄 **Проверка документа**\n\n"
            "Загрузите документ для анализа на соответствие российскому законодательству.\n\n"
            "📎 **Поддерживаемые форматы:**\n"
            "• PDF (.pdf)\n"
            "• Word (.docx, .doc)\n"
            "• Текстовые файлы (.txt)\n\n"
            "📏 **Максимальный размер:** 20 МБ\n\n"
            "⚖️ **Что проверяется:**\n"
            "• Соответствие формальным требованиям\n"
            "• Наличие обязательных реквизитов\n"
            "• Соответствие действующему законодательству\n"
            "• Выявление нарушений и несоответствий\n\n"
            "📎 Прикрепите файл следующим сообщением:",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'feedback':
        await query.edit_message_text(
            "💬 **Обратная связь**\n\n"
            "Ваше мнение важно для нас! Выберите тип обратной связи:",
            parse_mode='Markdown',
            reply_markup=feedback_menu()
        )
    
    elif query.data == 'settings':
        await query.edit_message_text(
            "⚙️ **Настройки**\n\n"
            "Персонализируйте работу бота под себя:",
            parse_mode='Markdown',
            reply_markup=settings_menu()
        )
    
    elif query.data == 'clear_history':
        if analytics:
            analytics.log_user_action(user_id, 'clear_history')
        
        # Очищаем историю чата
        if law_assistant and hasattr(law_assistant, 'store'):
            if user_id in law_assistant.store:
                del law_assistant.store[user_id]
        
        # Очищаем состояние пользователя
        if state_manager:
            state_manager.clear_user_state(user_id)
            state_manager.clear_last_answer(user_id)
        
        await query.edit_message_text(
            "🔄 **История очищена**\n\n"
            "✅ История ваших чатов успешно удалена.\n"
            "Теперь бот не помнит предыдущие вопросы и ответы.\n\n"
            "💡 Вы можете начать новый диалог с чистого листа.",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'documents_status':
        # Показываем статус документов
        if law_assistant and hasattr(law_assistant, 'get_documents_info'):
            docs_info = law_assistant.get_documents_info()
            
            message = "📚 **СТАТУС ДОКУМЕНТОВ**\n\n"
            
            if docs_info['base_vector_store_available']:
                message += "✅ **Базовая векторная база:** Доступна\n"
            else:
                message += "❌ **Базовая векторная база:** Недоступна\n"
            
            if docs_info['additional_documents_loaded']:
                stats = docs_info.get('stats', {})
                message += f"✅ **Дополнительные документы:** Загружены\n"
                message += f"📊 **Всего файлов:** {stats.get('total_files', 0)}\n\n"
                
                categories_names = {
                    'laws': '⚖️ Федеральные законы',
                    'codes': '📖 Кодексы РФ',
                    'articles': '📝 Юридические статьи',
                    'court_practice': '🏛️ Судебная практика'
                }
                
                message += "📋 **ПО КАТЕГОРИЯМ:**\n"
                for category, count in stats.get('categories', {}).items():
                    if count > 0:
                        name = categories_names.get(category, category)
                        message += f"{name}: **{count}** файлов\n"
            else:
                message += "📝 **Дополнительные документы:** Не найдены\n"
            
            message += "\n💡 Для добавления документов поместите файлы в папку `documents/`"
        else:
            message = "❌ **Информация о документах недоступна**\n\nСистема находится в режиме ограниченной функциональности."
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'back_to_main':
        # Очищаем состояние пользователя
        if state_manager:
            state_manager.clear_user_state(user_id)
        
        await query.edit_message_text(
            "🏠 **Главное меню**\n\n"
            "Выберите действие:",
            parse_mode='Markdown',
            reply_markup=main_menu()
        )
    
    # Обработка обратной связи
    elif query.data == 'rate_answer':
        last_answer = state_manager.get_last_answer(user_id) if state_manager else None
        
        if last_answer:
            await query.edit_message_text(
                "⭐ **Оцените качество ответа**\n\n"
                f"**Ваш вопрос:** {last_answer['question'][:100]}...\n\n"
                "Поставьте оценку от 1 до 5:",
                parse_mode='Markdown',
                reply_markup=rating_keyboard()
            )
        else:
            await query.edit_message_text(
                "❌ **Нет ответа для оценки**\n\n"
                "Сначала задайте вопрос, а затем оцените качество ответа.",
                parse_mode='Markdown',
                reply_markup=feedback_menu()
            )
    
    elif query.data.startswith('rate_'):
        # Обработка оценок
        if query.data in ['rate_1', 'rate_2', 'rate_3', 'rate_4', 'rate_5']:
            rating = int(query.data.split('_')[1])
            
            last_answer = state_manager.get_last_answer(user_id) if state_manager else None
            
            if last_answer and analytics:
                analytics.log_question_rating(user_id, last_answer['question'], rating)
                
                # Отправляем уведомление админу о низкой оценке
                if rating <= 2 and admin_notifier:
                    user_name = query.from_user.first_name or "Неизвестен"
                    await admin_notifier.send_low_rating_alert(
                        user_id, user_name, rating, last_answer['question']
                    )
            
            await query.edit_message_text(
                f"⭐ **Спасибо за оценку!**\n\n"
                f"Вы поставили: **{rating}/5** {'⭐' * rating}\n\n"
                "Ваша обратная связь поможет нам улучшить качество ответов.",
                parse_mode='Markdown',
                reply_markup=back_to_main_button()
            )
        
        elif query.data == 'rate_helpful':
            await query.edit_message_text(
                "👍 **Отлично!**\n\n"
                "Рады, что смогли помочь! Обращайтесь снова, если возникнут вопросы.",
                parse_mode='Markdown',
                reply_markup=back_to_main_button()
            )
        
        elif query.data == 'rate_not_helpful':
            if state_manager:
                state_manager.set_user_state(user_id, 'waiting_for_feedback')
            
            await query.edit_message_text(
                "👎 **Жаль, что не помогли**\n\n"
                "Расскажите, что можно улучшить? Ваш отзыв поможет нам стать лучше.\n\n"
                "✍️ Напишите ваши предложения следующим сообщением:",
                parse_mode='Markdown',
                reply_markup=back_to_main_button()
            )
    
    elif query.data == 'report_bug':
        if state_manager:
            state_manager.set_user_state(user_id, 'waiting_for_bug_report')
        
        await query.edit_message_text(
            "🐛 **Сообщить об ошибке**\n\n"
            "Опишите проблему, с которой вы столкнулись:\n\n"
            "💡 **Укажите:**\n"
            "• Что вы делали\n"
            "• Что произошло\n"
            "• Что ожидали увидеть\n\n"
            "✍️ Напишите описание проблемы следующим сообщением:",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'suggest_improvement':
        if state_manager:
            state_manager.set_user_state(user_id, 'waiting_for_suggestion')
        
        await query.edit_message_text(
            "💡 **Предложить улучшение**\n\n"
            "Поделитесь идеями, как сделать бота лучше:\n\n"
            "🎯 **Например:**\n"
            "• Новые функции\n"
            "• Улучшения интерфейса\n"
            "• Дополнительные возможности\n\n"
            "✍️ Напишите ваше предложение следующим сообщением:",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    # Настройки
    elif query.data == 'settings_stats':
        if analytics:
            user_stats = analytics.get_user_stats(user_id)
            token_stats = analytics.get_user_token_stats(user_id)
            
            message = f"📊 **ВАША СТАТИСТИКА**\n\n"
            message += f"❓ **Задано вопросов:** {user_stats.get('ask_question', 0)}\n"
            message += f"📄 **Проверено документов:** {user_stats.get('check_document', 0)}\n"
            message += f"⭐ **Оценок поставлено:** {user_stats.get('rate_answer', 0)}\n"
            message += f"🔄 **Всего действий:** {user_stats.get('total_actions', 0)}\n\n"
            
            if token_stats:
                message += f"🤖 **ИСПОЛЬЗОВАНИЕ ИИ:**\n"
                message += f"• Всего токенов: {token_stats.get('total_tokens', 0):,}\n"
                message += f"• Запросов к ИИ: {token_stats.get('requests_count', 0)}\n"
                
                if token_stats.get('total_tokens', 0) > 0:
                    cost = analytics.calculate_token_cost(
                        token_stats.get('prompt_tokens', 0),
                        token_stats.get('completion_tokens', 0)
                    )
                    message += f"• Примерная стоимость: ${cost:.4f}\n"
        else:
            message = "❌ Статистика недоступна"
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=settings_menu()
        )
    
    elif query.data == 'export_history':
        if user_manager:
            history_json = user_manager.export_user_history(user_id)
            
            if history_json:
                # Создаем временный файл
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                    f.write(history_json)
                    temp_file = f.name
                
                try:
                    # Отправляем файл
                    with open(temp_file, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=query.message.chat_id,
                            document=f,
                            filename=f"neuralex_history_{user_id}_{datetime.now().strftime('%Y%m%d')}.json",
                            caption="📝 **Ваша история чатов**\n\nВ файле содержится вся история ваших диалогов с ботом."
                        )
                    
                    await query.edit_message_text(
                        "✅ **История экспортирована**\n\n"
                        "Файл с вашей историей чатов отправлен выше.",
                        parse_mode='Markdown',
                        reply_markup=settings_menu()
                    )
                finally:
                    # Удаляем временный файл
                    os.unlink(temp_file)
            else:
                await query.edit_message_text(
                    "❌ **Ошибка экспорта**\n\n"
                    "Не удалось экспортировать историю. Возможно, у вас еще нет сохраненных диалогов.",
                    parse_mode='Markdown',
                    reply_markup=settings_menu()
                )
        else:
            await query.edit_message_text(
                "❌ Экспорт недоступен",
                reply_markup=settings_menu()
            )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик загруженных документов"""
    user_id = str(update.effective_user.id)
    
    # Проверяем состояние пользователя
    current_state = state_manager.get_user_state(user_id) if state_manager else None
    
    if current_state != 'waiting_for_document':
        await update.message.reply_text(
            "❌ Для проверки документа сначала нажмите кнопку '📄 Проверить документ' в главном меню.",
            reply_markup=main_menu()
        )
        return
    
    # Проверяем rate limiting
    if not rate_limiter.is_allowed(user_id):
        remaining_time = rate_limiter.get_reset_time(user_id)
        await update.message.reply_text(
            f"⏳ Превышен лимит запросов. Попробуйте через {int(remaining_time)} секунд.",
            reply_markup=back_to_main_button()
        )
        return
    
    document = update.message.document
    
    # Проверяем размер файла
    if document.file_size > MAX_FILE_SIZE:
        await update.message.reply_text(
            f"❌ **Файл слишком большой**\n\n"
            f"Максимальный размер: {MAX_FILE_SIZE // (1024*1024)} МБ\n"
            f"Размер вашего файла: {document.file_size // (1024*1024)} МБ\n\n"
            "Попробуйте загрузить файл меньшего размера.",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
        return
    
    # Проверяем расширение файла
    file_extension = os.path.splitext(document.file_name)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        await update.message.reply_text(
            f"❌ **Неподдерживаемый формат файла**\n\n"
            f"Поддерживаемые форматы: {', '.join(ALLOWED_EXTENSIONS)}\n"
            f"Ваш файл: {file_extension}\n\n"
            "Пожалуйста, конвертируйте файл в один из поддерживаемых форматов.",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
        return
    
    # Отправляем сообщение о начале обработки
    processing_message = await update.message.reply_text(
        "⏳ **Обрабатываю документ...**\n\n"
        "📄 Загружаю файл\n"
        "🔍 Извлекаю текст\n"
        "⚖️ Анализирую на соответствие законодательству\n\n"
        "Это может занять несколько минут...",
        parse_mode='Markdown'
    )
    
    try:
        # Загружаем файл
        file = await context.bot.get_file(document.file_id)
        
        # Создаем временный файл
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            await file.download_to_drive(temp_file.name)
            temp_file_path = temp_file.name
        
        try:
            # Извлекаем текст
            document_text = extract_text_from_file(temp_file_path, file_extension)
            
            if not document_text or len(document_text.strip()) < 50:
                await processing_message.edit_text(
                    "❌ **Не удалось извлечь текст**\n\n"
                    "Возможные причины:\n"
                    "• Файл поврежден\n"
                    "• Файл содержит только изображения\n"
                    "• Файл пустой или содержит мало текста\n\n"
                    "Попробуйте загрузить другой файл.",
                    parse_mode='Markdown',
                    reply_markup=back_to_main_button()
                )
                return
            
            # Обновляем сообщение
            await processing_message.edit_text(
                "🔍 **Анализирую документ...**\n\n"
                f"📄 Файл: {document.file_name}\n"
                f"📊 Размер: {len(document_text)} символов\n"
                f"⚖️ Проверяю соответствие российскому законодательству...",
                parse_mode='Markdown'
            )
            
            # Анализируем документ
            analysis_result = analyze_document(document_text)
            
            # Логируем действие
            if analytics:
                analytics.log_user_action(user_id, 'check_document', {
                    'filename': document.file_name,
                    'file_size': document.file_size,
                    'file_extension': file_extension
                })
            
            # Очищаем состояние
            if state_manager:
                state_manager.clear_user_state(user_id)
            
            # Отправляем результат
            await processing_message.edit_text(
                f"📋 **АНАЛИЗ ДОКУМЕНТА ЗАВЕРШЕН**\n\n"
                f"📄 **Файл:** {document.file_name}\n"
                f"📊 **Размер:** {document.file_size // 1024} КБ\n\n"
                f"{analysis_result}",
                parse_mode='Markdown',
                reply_markup=back_to_main_button()
            )
            
        finally:
            # Удаляем временный файл
            try:
                os.unlink(temp_file_path)
            except Exception as delete_error:
                logger.error(f"Ошибка при удалении временного файла: {delete_error}")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке документа: {e}")
        
        try:
            await processing_message.edit_text(
                "❌ **Ошибка при обработке документа**\n\n"
                "Произошла техническая ошибка. Попробуйте:\n"
                "• Загрузить файл еще раз\n"
                "• Проверить формат файла\n"
                "• Обратиться в поддержку\n\n"
                "Приносим извинения за неудобства.",
                parse_mode='Markdown',
                reply_markup=back_to_main_button()
            )
        except Exception as edit_error:
            logger.error(f"Ошибка при редактировании сообщения: {edit_error}")
            
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке документа. Попробуйте позже.",
                reply_markup=back_to_main_button()
            )

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений пользователя"""
    user_id = str(update.effective_user.id)
    message_text = update.message.text
    
    # Обновляем активность пользователя
    if user_manager:
        user_manager.update_last_activity(user_id)
    
    # Получаем текущее состояние пользователя
    current_state = state_manager.get_user_state(user_id) if state_manager else None
    
    if current_state == 'waiting_for_question':
        await process_legal_question(update, context, message_text, user_id)
    elif current_state == 'waiting_for_bug_report':
        await process_bug_report(update, context, message_text, user_id)
    elif current_state == 'waiting_for_suggestion':
        await process_improvement_suggestion(update, context, message_text, user_id)
    elif current_state == 'waiting_for_feedback':
        await process_feedback(update, context, message_text, user_id)
    else:
        # Пользователь отправил сообщение без контекста
        await update.message.reply_text(
            "🤔 **Не понимаю, что вы хотите сделать**\n\n"
            "Используйте кнопки меню для выбора действия:\n"
            "• ❓ Задать вопрос - для юридической консультации\n"
            "• 📄 Проверить документ - для анализа документов\n"
            "• 💬 Обратная связь - для отзывов и предложений\n\n"
            "Или напишите /start для возврата в главное меню.",
            parse_mode='Markdown',
            reply_markup=main_menu()
        )

async def process_legal_question(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str, user_id: str):
    """Обрабатывает юридический вопрос пользователя"""
    
    # Проверяем rate limiting
    if not rate_limiter.is_allowed(user_id):
        remaining_time = rate_limiter.get_reset_time(user_id)
        await update.message.reply_text(
            f"⏳ Превышен лимит запросов. Попробуйте через {int(remaining_time)} секунд.",
            reply_markup=back_to_main_button()
        )
        return
    
    # Проверяем длину вопроса
    if len(question.strip()) < 10:
        await update.message.reply_text(
            "❓ **Вопрос слишком короткий**\n\n"
            "Пожалуйста, опишите вашу ситуацию более подробно. "
            "Чем больше деталей вы предоставите, тем точнее будет ответ.\n\n"
            "Попробуйте еще раз:",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
        return
    
    # Отправляем индикатор печати
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # Отправляем сообщение о начале обработки
    processing_message = await update.message.reply_text(
        "🤖 **Анализирую ваш вопрос...**\n\n"
        "🔍 Ищу релевантную информацию в правовой базе\n"
        "⚖️ Формирую юридическое заключение\n\n"
        "Это займет несколько секунд...",
        parse_mode='Markdown'
    )
    
    try:
        if not law_assistant:
            await processing_message.edit_text(
                "❌ **ИИ-юрист временно недоступен**\n\n"
                "Система находится в режиме технического обслуживания. "
                "Попробуйте задать вопрос позже.\n\n"
                "Приносим извинения за неудобства.",
                parse_mode='Markdown',
                reply_markup=back_to_main_button()
            )
            return
        
        # Получаем ответ от ИИ
        answer, chat_history = law_assistant.conversational(question, user_id)
        
        # Сохраняем последний ответ для возможной оценки
        if state_manager:
            state_manager.save_last_answer(user_id, question, answer)
        
        # Очищаем состояние
        if state_manager:
            state_manager.clear_user_state(user_id)
        
        # Логируем действие
        if analytics:
            analytics.log_user_action(user_id, 'ask_question', {
                'question_length': len(question),
                'answer_length': len(answer)
            })
        
        # Отправляем ответ
        await processing_message.edit_text(
            f"⚖️ **ЮРИДИЧЕСКАЯ КОНСУЛЬТАЦИЯ**\n\n"
            f"**Ваш вопрос:** {question[:100]}{'...' if len(question) > 100 else ''}\n\n"
            f"{answer}\n\n"
            f"---\n"
            f"💡 *Это консультация носит информационный характер. "
            f"Для решения серьезных правовых вопросов обратитесь к квалифицированному юристу.*",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке вопроса пользователя {user_id}: {e}")
        
        # Проверяем тип ошибки
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['openai', 'api key', 'rate limit', 'quota']):
            error_message = (
                "❌ **Проблема с ИИ-сервисом**\n\n"
                "Возможные причины:\n"
                "• Превышен лимит запросов к OpenAI\n"
                "• Проблемы с API ключом\n"
                "• Временные неполадки сервиса\n\n"
                "Попробуйте задать вопрос через несколько минут."
            )
        else:
            error_message = (
                "❌ **Произошла техническая ошибка**\n\n"
                "Не удалось обработать ваш вопрос. Попробуйте:\n"
                "• Переформулировать вопрос\n"
                "• Задать вопрос позже\n"
                "• Обратиться в поддержку\n\n"
                "Приносим извинения за неудобства."
            )
        
        try:
            await processing_message.edit_text(
                error_message,
                parse_mode='Markdown',
                reply_markup=back_to_main_button()
            )
        except Exception as edit_error:
            logger.error(f"Ошибка при редактировании сообщения об ошибке: {edit_error}")
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке вопроса. Попробуйте позже.",
                reply_markup=back_to_main_button()
            )

async def process_bug_report(update: Update, context: ContextTypes.DEFAULT_TYPE, report: str, user_id: str):
    """Обрабатывает отчет об ошибке"""
    
    if len(report.strip()) < 10:
        await update.message.reply_text(
            "🐛 **Описание слишком короткое**\n\n"
            "Пожалуйста, опишите проблему более подробно. "
            "Это поможет нам быстрее найти и исправить ошибку.\n\n"
            "Попробуйте еще раз:",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
        return
    
    # Сохраняем отчет
    if analytics:
        analytics.log_user_action(user_id, 'bug_report', {'report': report})
    
    # Сохраняем в Redis для админа
    if analytics and analytics.redis_client:
        try:
            bug_data = {
                'user_id': user_id,
                'report': report,
                'timestamp': datetime.now().isoformat(),
                'type': 'bug_report'
            }
            key = f"feedback:bug:{user_id}:{datetime.now().timestamp()}"
            analytics.redis_client.setex(key, 7 * 24 * 3600, json.dumps(bug_data, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Ошибка при сохранении отчета об ошибке: {e}")
    
    # Отправляем уведомление администратору
    if admin_notifier:
        user_name = update.effective_user.first_name or "Неизвестен"
        await admin_notifier.send_bug_report(user_id, user_name, report)
    
    # Очищаем состояние
    if state_manager:
        state_manager.clear_user_state(user_id)
    
    await update.message.reply_text(
        "✅ **Отчет об ошибке отправлен**\n\n"
        "Спасибо за ваш отчет! Мы рассмотрим проблему и постараемся исправить её в ближайшее время.\n\n"
        "📧 Если потребуется дополнительная информация, мы свяжемся с вами.",
        parse_mode='Markdown',
        reply_markup=back_to_main_button()
    )

async def process_improvement_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE, suggestion: str, user_id: str):
    """Обрабатывает предложение по улучшению"""
    
    if len(suggestion.strip()) < 10:
        await update.message.reply_text(
            "💡 **Предложение слишком короткое**\n\n"
            "Пожалуйста, опишите ваше предложение более подробно. "
            "Чем детальнее описание, тем лучше мы сможем его реализовать.\n\n"
            "Попробуйте еще раз:",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
        return
    
    # Сохраняем предложение
    if analytics:
        analytics.log_user_action(user_id, 'improvement_suggestion', {'suggestion': suggestion})
    
    # Сохраняем в Redis для админа
    if analytics and analytics.redis_client:
        try:
            suggestion_data = {
                'user_id': user_id,
                'suggestion': suggestion,
                'timestamp': datetime.now().isoformat(),
                'type': 'improvement_suggestion'
            }
            key = f"feedback:suggestion:{user_id}:{datetime.now().timestamp()}"
            analytics.redis_client.setex(key, 7 * 24 * 3600, json.dumps(suggestion_data, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Ошибка при сохранении предложения: {e}")
    
    # Отправляем уведомление администратору
    if admin_notifier:
        user_name = update.effective_user.first_name or "Неизвестен"
        await admin_notifier.send_improvement_suggestion(user_id, user_name, suggestion)
    
    # Очищаем состояние
    if state_manager:
        state_manager.clear_user_state(user_id)
    
    await update.message.reply_text(
        "✅ **Предложение отправлено**\n\n"
        "Спасибо за ваше предложение! Мы обязательно рассмотрим его при планировании новых функций.\n\n"
        "🚀 Лучшие идеи будут реализованы в следующих обновлениях!",
        parse_mode='Markdown',
        reply_markup=back_to_main_button()
    )

async def process_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE, feedback: str, user_id: str):
    """Обрабатывает общую обратную связь"""
    
    if len(feedback.strip()) < 5:
        await update.message.reply_text(
            "💬 **Отзыв слишком короткий**\n\n"
            "Пожалуйста, напишите более подробный отзыв.\n\n"
            "Попробуйте еще раз:",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
        return
    
    # Сохраняем отзыв
    if analytics:
        analytics.log_user_action(user_id, 'feedback', {'feedback': feedback})
    
    # Очищаем состояние
    if state_manager:
        state_manager.clear_user_state(user_id)
    
    await update.message.reply_text(
        "✅ **Спасибо за отзыв!**\n\n"
        "Ваше мнение очень важно для нас. Мы учтем ваши замечания для улучшения работы бота.\n\n"
        "🙏 Благодарим за помощь в развитии проекта!",
        parse_mode='Markdown',
        reply_markup=back_to_main_button()
    )