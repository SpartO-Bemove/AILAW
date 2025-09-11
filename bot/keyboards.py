from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    """Главное меню бота"""
    keyboard = [
        [InlineKeyboardButton("❓ Задать вопрос", callback_data='ask'),
         InlineKeyboardButton("📄 Проверить документ", callback_data='check_document')],
        [InlineKeyboardButton("📚 Справочник законов", callback_data='laws'),
         InlineKeyboardButton("🔍 Быстрый поиск", callback_data='quick_search')],
        [InlineKeyboardButton("📊 Популярные вопросы", callback_data='popular_questions'),
         InlineKeyboardButton("💡 Примеры вопросов", callback_data='question_examples')],
        [InlineKeyboardButton("⚙️ Настройки", callback_data='settings'),
         InlineKeyboardButton("💬 Обратная связь", callback_data='feedback')],
        [InlineKeyboardButton("ℹ️ О боте", callback_data='about'),
         InlineKeyboardButton("🔄 Очистить историю", callback_data='clear_history')],
        [InlineKeyboardButton("📚 Статус документов", callback_data='documents_status')]
    ]
    return InlineKeyboardMarkup(keyboard)

def laws_menu():
    """Меню с категориями законов"""
    keyboard = [
        [InlineKeyboardButton("⚖️ Конституция РФ", callback_data='law_constitution'),
         InlineKeyboardButton("🏛️ Гражданский кодекс", callback_data='law_civil')],
        [InlineKeyboardButton("⚔️ Уголовный кодекс", callback_data='law_criminal'),
         InlineKeyboardButton("💼 Трудовой кодекс", callback_data='law_labor')],
        [InlineKeyboardButton("👨‍👩‍👧‍👦 Семейный кодекс", callback_data='law_family'),
         InlineKeyboardButton("💰 Налоговый кодекс", callback_data='law_tax')],
        [InlineKeyboardButton("🏠 Жилищный кодекс", callback_data='law_housing'),
         InlineKeyboardButton("🚗 КоАП РФ", callback_data='law_koap')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_to_main_button():
    """Кнопка возврата в главное меню"""
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='back_to_main')]]
    return InlineKeyboardMarkup(keyboard)

def settings_menu():
    """Меню настроек пользователя"""
    keyboard = [
        [InlineKeyboardButton("🔔 Уведомления", callback_data='settings_notifications')],
        [InlineKeyboardButton("📊 Статистика", callback_data='settings_stats')],
        [InlineKeyboardButton("🌐 Язык", callback_data='settings_language')],
        [InlineKeyboardButton("📝 Экспорт истории", callback_data='export_history')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def feedback_menu():
    """Меню обратной связи"""
    keyboard = [
        [InlineKeyboardButton("⭐ Оценить ответ", callback_data='rate_answer')],
        [InlineKeyboardButton("🐛 Сообщить об ошибке", callback_data='report_bug')],
        [InlineKeyboardButton("💡 Предложить улучшение", callback_data='suggest_improvement')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def quick_actions_menu():
    """Меню быстрых действий"""
    keyboard = [
        [InlineKeyboardButton("⚡ Трудовые споры", callback_data='quick_labor')],
        [InlineKeyboardButton("🏠 Жилищные вопросы", callback_data='quick_housing')],
        [InlineKeyboardButton("👨‍👩‍👧‍👦 Семейное право", callback_data='quick_family')],
        [InlineKeyboardButton("💰 Налоги и финансы", callback_data='quick_tax')],
        [InlineKeyboardButton("🚗 ДТП и штрафы", callback_data='quick_traffic')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def question_examples_menu():
    """Меню с примерами вопросов"""
    keyboard = [
        [InlineKeyboardButton("💼 Как уволиться правильно?", callback_data='example_quit')],
        [InlineKeyboardButton("🏠 Права арендатора", callback_data='example_rent')],
        [InlineKeyboardButton("👶 Алименты на ребенка", callback_data='example_alimony')],
        [InlineKeyboardButton("🚗 Что делать при ДТП?", callback_data='example_accident')],
        [InlineKeyboardButton("💰 Возврат товара в магазин", callback_data='example_return')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def rating_keyboard():
    """Клавиатура для оценки ответа"""
    keyboard = [
        [
            InlineKeyboardButton("1️⃣", callback_data='rate_1'),
            InlineKeyboardButton("2️⃣", callback_data='rate_2'),
            InlineKeyboardButton("3️⃣", callback_data='rate_3'),
            InlineKeyboardButton("4️⃣", callback_data='rate_4'),
            InlineKeyboardButton("5️⃣", callback_data='rate_5')
        ],
        [InlineKeyboardButton("👍 Полезно", callback_data='rate_helpful'),
         InlineKeyboardButton("👎 Не помогло", callback_data='rate_not_helpful')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)