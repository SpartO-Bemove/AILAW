@@ .. @@
 # Проверяем формат токенов
 if TOKEN and not TOKEN.startswith(('1', '2', '5', '6', '7')):
     logging.warning("TELEGRAM_BOT_TOKEN имеет подозрительный формат")
+
+if OPENAI_API_KEY and not OPENAI_API_KEY.startswith('sk-'):
+    logging.warning("OPENAI_API_KEY должен начинаться с 'sk-'")
+
 # Настройки бота
 MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 МБ
 ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt']
 CHROMA_DB_PATH = "chroma_db_legal_bot_part1"
 
 # ID администратора для получения уведомлений (замените на ваш Telegram ID)
 ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
 
 # Настройки уведомлений
 ENABLE_ADMIN_NOTIFICATIONS = os.getenv('ENABLE_ADMIN_NOTIFICATIONS', 'true').lower() == 'true'
 
-if OPENAI_API_KEY and not OPENAI_API_KEY.startswith('sk-'):
-    logging.warning("OPENAI_API_KEY должен начинаться с 'sk-'")
-
 logging.info("Конфигурация бота загружена успешно")