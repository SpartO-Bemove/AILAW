import sys
import os
import logging

# Добавляем путь к neuralex-main в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'neuralex-main'))

from telegram import Update
from telegram import Document
from telegram.ext import ContextTypes

from .keyboards import main_menu, laws_menu, back_to_main_button

try:
    from neuralex_main import neuralex
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain_community.vectorstores import Chroma
    import os
    import fitz  # PyMuPDF для работы с PDF
    import docx  # python-docx для работы с Word
    import tempfile
    import asyncio
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Настройка логирования для handlers
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Инициализация компонентов neuralex
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
    
    llm = ChatOpenAI(model='gpt-4o-mini', temperature=0.9, openai_api_key=openai_api_key)
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    vector_store = Chroma(persist_directory="chroma_db_legal_bot_part1", embedding_function=embeddings)
    
    # Создаем экземпляр neuralex
    law_assistant = neuralex(llm, embeddings, vector_store)
    
    logger.info("Neuralex компоненты успешно инициализированы")
    
except ImportError as e:
    logging.error(f"Ошибка импорта neuralex: {e}")
    law_assistant = None
except Exception as e:
    logging.error(f"Ошибка инициализации neuralex: {e}")
    law_assistant = None

# Словарь для отслеживания состояния пользователей
user_states = {}

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
    if law_assistant is None:
        return "❌ Сервис анализа документов временно недоступен."
    
    analysis_prompt = f"""
Проанализируй следующий документ на соответствие российскому законодательству:

ДОКУМЕНТ:
{document_text[:4000]}  # Ограничиваем размер для анализа

Проведи анализ по следующим критериям:
1. Соответствие формальным требованиям
2. Наличие обязательных реквизитов
3. Соответствие действующему законодательству
4. Выявленные нарушения или несоответствия
5. Рекомендации по исправлению

Дай краткое заключение о юридической корректности документа.
"""
    
    try:
        answer, _ = law_assistant.conversational(analysis_prompt, user_id)
        return answer
    except Exception as e:
        logging.error(f"Ошибка при анализе документа: {e}")
        return "❌ Произошла ошибка при анализе документа. Попробуйте позже."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name or "Пользователь"
    
    # Сбрасываем состояние пользователя при старте
    user_states[user_id] = None
    
    logging.info(f"Пользователь {user_name} (ID: {user_id}) запустил бота")
    
    welcome_text = f"""
👋 Привет, {user_name}!

Я **Neuralex** — ваш персональный ИИ-юрист, специализирующийся на российском законодательстве.

🎯 **Что я умею:**
• Отвечать на юридические вопросы
• Объяснять статьи законов простым языком
• Помогать разобраться в правовых ситуациях
• Предоставлять ссылки на конкретные нормы права

⚖️ **Моя база знаний включает:**
• Конституцию РФ
• Гражданский, Уголовный, Трудовой кодексы
• Семейный, Налоговый, Жилищный кодексы
• КоАП РФ и другие федеральные законы

Выберите действие:
    """
    await update.message.reply_text(welcome_text, reply_markup=main_menu())

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик загруженных документов"""
    user_id = str(update.effective_user.id)
    
    # Проверяем состояние пользователя
    if user_states.get(user_id) != 'checking_document':
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
        user_states[user_id] = None
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
        user_states[user_id] = None
        return
    
    # Показываем индикатор обработки
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
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
            user_states[user_id] = None
            return
        
        logging.info(f"Анализ документа для пользователя {user_id}: {document.file_name}")
        
        # Анализируем документ
        analysis_result = await analyze_document(document_text, user_id)
        
        # Форматируем ответ
        formatted_response = f"""📄 **Анализ документа: {document.file_name}**

📊 **Размер файла:** {document.file_size / 1024:.1f} КБ
📝 **Тип файла:** {file_extension.upper()}
📏 **Длина текста:** {len(document_text)} символов

⚖️ **Юридический анализ:**

{analysis_result}

⚠️ *Данный анализ носит справочный характер. Для окончательного заключения обратитесь к квалифицированному юристу.*"""
        
        await update.message.reply_text(
            formatted_response,
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
        
        # Сбрасываем состояние пользователя
        user_states[user_id] = None
        
    except Exception as e:
        logging.error(f"Ошибка при обработке документа для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке документа. Попробуйте еще раз.",
            reply_markup=main_menu()
        )
        user_states[user_id] = None

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений пользователя"""
    user_id = str(update.effective_user.id)
    user_text = update.message.text
    
    # Проверяем состояние пользователя
    if user_states.get(user_id) == 'asking_question':
        # Обрабатываем вопрос
        await process_legal_question(update, context, user_text, user_id)
    elif user_states.get(user_id) == 'checking_document':
        await update.message.reply_text(
            "📄 Пожалуйста, загрузите документ для проверки.\n\n"
            "Поддерживаемые форматы: PDF, DOCX, DOC, TXT\n"
            "Максимальный размер: 20 МБ",
            reply_markup=back_to_main_button()
        )
    else:
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки для навигации.",
            reply_markup=main_menu()
        )

async def process_legal_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str, user_id: str):
    """Обрабатывает юридический вопрос пользователя"""
    
    if law_assistant is None:
        await update.message.reply_text(
            "❌ Извините, сервис временно недоступен. Попробуйте позже.",
            reply_markup=main_menu()
        )
        user_states[user_id] = None
        return
    
    # Показываем индикатор печати
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    logging.info(f"Обработка вопроса от пользователя {user_id}: {user_text[:100]}...")
    
    try:
        # Получаем ответ от ИИ-юриста
        answer, _ = law_assistant.conversational(user_text, user_id)
        
        # Форматируем ответ
        formatted_answer = f"⚖️ **Юридическая консультация:**\n\n{answer}\n\n"
        formatted_answer += "⚠️ *Данная информация носит справочный характер. Для решения серьезных правовых вопросов обратитесь к квалифицированному юристу.*"
        
        await update.message.reply_text(
            formatted_answer,
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
        
        logging.info(f"Успешно обработан вопрос пользователя {user_id}")
        
        # Сбрасываем состояние пользователя
        user_states[user_id] = None
        
    except Exception as e:
        logging.error(f"Ошибка при обработке запроса пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке вашего запроса. Попробуйте еще раз.",
            reply_markup=main_menu()
        )
        user_states[user_id] = None

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name or "Пользователь"
    
    logging.info(f"Пользователь {user_name} (ID: {user_id}) нажал кнопку: {query.data}")
    
    if query.data == 'ask':
        user_states[user_id] = 'asking_question'
        await query.edit_message_text(
            "❓ **Задайте ваш юридический вопрос**\n\n"
            "Опишите вашу ситуацию максимально подробно. Чем больше деталей вы предоставите, "
            "тем более точный и полезный ответ я смогу дать.\n\n"
            "📝 *Например:*\n"
            "• Какие права имеет работник при увольнении?\n"
            "• Как оформить развод через ЗАГС?\n"
            "• Какая ответственность за нарушение ПДД?\n\n"
            "Напишите ваш вопрос в следующем сообщении:",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'check_document':
        user_states[user_id] = 'checking_document'
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
        await query.edit_message_text(
            "📚 **Доступные категории законов:**\n\n"
            "Выберите интересующую вас область права для получения общей информации:",
            parse_mode='Markdown',
            reply_markup=laws_menu()
        )
    
    elif query.data == 'about':
        about_text = """
ℹ️ **О боте Neuralex**

🤖 **Версия:** 1.0 (Пилотная)
🧠 **ИИ-модель:** GPT-4o-mini
📊 **База данных:** Векторная база российского законодательства

🎯 **Возможности:**
• Консультации по российскому праву
• Поиск по базе законов
• Объяснение правовых норм
• Персонализированная история чатов

⚠️ **Важно:**
Бот находится в пилотной фазе. Ответы могут быть неточными на 100%. Для серьезных юридических вопросов обращайтесь к квалифицированным юристам.

🔧 **Техподдержка:** @your_support_bot
        """
        await query.edit_message_text(
            about_text,
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'clear_history':
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
        law_info = get_law_info(query.data)
        await query.edit_message_text(
            law_info,
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )
    
    elif query.data == 'back_to_main':
        user_states[user_id] = None  # Сбрасываем состояние
        await query.edit_message_text(
            f"👋 С возвращением, {user_name}!\n\nВыберите действие:",
            reply_markup=main_menu()
        )
    
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