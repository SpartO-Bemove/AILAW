@@ .. @@
 def laws_menu():
     """Меню с категориями законов"""
     keyboard = [
         [InlineKeyboardButton("⚖️ Конституция РФ", callback_data='law_constitution'),
          InlineKeyboardButton("🏛️ Гражданский кодекс", callback_data='law_civil')],
         [InlineKeyboardButton("⚔️ Уголовный кодекс", callback_data='law_criminal'),
          InlineKeyboardButton("💼 Трудовой кодекс", callback_data='law_labor')],
         [InlineKeyboardButton("👨‍👩‍👧‍👦 Семейный кодекс", callback_data='law_family'),
          InlineKeyboardButton("💰 Налоговый кодекс", callback_data='law_tax')],
         [InlineKeyboardButton("🏠 Жилищный кодекс", callback_data='law_housing')],
         [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
     ]
     return InlineKeyboardMarkup(keyboard)