@@ .. @@
         try:
             from .handlers import law_assistant
             
             if not law_assistant:
                 await query.edit_message_text(
                     "❌ Law assistant недоступен",
                     reply_markup=self.admin_panel.get_documents_menu()
                 )
                 return
             
             docs_info = law_assistant.get_documents_info()
             stats = docs_info.get('stats', {})
             
             message = "📚 **СТАТУС ДОКУМЕНТОВ**\n\n"
             
             if docs_info['additional_documents_loaded']:
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
                     name = categories_names.get(category, category)
                     message += f"{name}: **{count}** файлов\n"
                 
             else:
                 message += "📝 **Дополнительные документы:** Не найдены\n"
                 message += "💡 Добавьте файлы в папку `documents/`\n"
             
             if docs_info['base_vector_store_available']:
                 message += "\n✅ **Базовая векторная база:** Доступна"
             else:
                 message += "\n❌ **Базовая векторная база:** Недоступна"
             
             await query.edit_message_text(
                 message,
                 parse_mode='Markdown',
                 reply_markup=self.admin_panel.get_documents_menu()
             )
             
         except Exception as e:
             logger.error(f"Ошибка при показе статуса документов: {e}")
             await query.edit_message_text(
                 "❌ Ошибка при загрузке статуса документов",
                 reply_markup=self.admin_panel.get_documents_menu()
             )