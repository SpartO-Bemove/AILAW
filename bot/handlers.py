import sys
import os

# Добавляем путь к neuralex-main в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'neuralex-main'))

from telegram import Update
from telegram.ext import ContextTypes

from .keyboards import main_menu, laws_menu, back_to_main_button

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

# Словарь для отслеживания состояния пользователей
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_name = update.effective_user.first_name or "Пользователь"
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

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений пользователя"""
    user_id = str(update.effective_user.id)
    user_text = update.message.text
    
    # Проверяем состояние пользователя
    if user_states.get(user_id) != 'asking_question':
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки для навигации или нажмите '❓ Задать вопрос' для отправки запроса.",
            reply_markup=main_menu()
        )
        return
    
    if law_assistant is None:
        await update.message.reply_text(
            "❌ Извините, сервис временно недоступен. Попробуйте позже.",
            reply_markup=main_menu()
        )
        return
    
    # Показываем индикатор печати
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
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
        
        # Сбрасываем состояние пользователя
        user_states[user_id] = None
        
    except Exception as e:
        print(f"Ошибка при обработке запроса: {e}")
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
            except Exception as e:
                print(f"Ошибка при очистке истории: {e}")
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
        user_name = update.effective_user.first_name or "Пользователь"
        await query.edit_message_text(
            f"👋 С возвращением, {user_name}!\n\nВыберите действие:",
            reply_markup=main_menu()
        )

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