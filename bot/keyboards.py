from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    """Главное меню бота"""
    keyboard = [
        [InlineKeyboardButton("❓ Задать вопрос", callback_data='ask')],
        [InlineKeyboardButton("📄 Проверить документ", callback_data='check_document')],
        [InlineKeyboardButton("📚 Посмотреть законы", callback_data='laws')],
        [InlineKeyboardButton("⚙️ Настройки", callback_data='settings')],
        [InlineKeyboardButton("💬 Обратная связь", callback_data='feedback')],
        [InlineKeyboardButton("ℹ️ О боте", callback_data='about')],
        [InlineKeyboardButton("🔄 Очистить историю", callback_data='clear_history')]
    ]
    return InlineKeyboardMarkup(keyboard)

def laws_menu():
    """Меню с категориями законов"""
    keyboard = [
        [InlineKeyboardButton("⚖️ Конституция РФ", callback_data='law_constitution')],
        [InlineKeyboardButton("🏛️ Гражданский кодекс", callback_data='law_civil')],
        [InlineKeyboardButton("⚔️ Уголовный кодекс", callback_data='law_criminal')],
        [InlineKeyboardButton("💼 Трудовой кодекс", callback_data='law_labor')],
        [InlineKeyboardButton("👨‍👩‍👧‍👦 Семейный кодекс", callback_data='law_family')],
        [InlineKeyboardButton("💰 Налоговый кодекс", callback_data='law_tax')],
        [InlineKeyboardButton("🏠 Жилищный кодекс", callback_data='law_housing')],
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

def rating_keyboard():
    """Клавиатура для оценки ответа"""
    keyboard = [
        [
            InlineKeyboardButton("⭐", callback_data='rate_1'),
            InlineKeyboardButton("⭐⭐", callback_data='rate_2'),
            InlineKeyboardButton("⭐⭐⭐", callback_data='rate_3'),
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data='rate_4'),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data='rate_5')
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)