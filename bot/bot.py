import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from .config import TOKEN
from .handlers import start, button_handler, handle_user_message, handle_document
from .scheduler import scheduler

logger = logging.getLogger(__name__)

def main():
    """Основная функция запуска бота"""
    try:
        print("🚀 Запуск телеграм-бота Neuralex...")
        
        # Запускаем планировщик
        scheduler.start()
        print("✅ Планировщик запущен")
        
        app = Application.builder().token(TOKEN).build()
        print("✅ Telegram Application создан")

        # Добавляем обработчики
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))
        print("✅ Обработчики добавлены")

        logger.info("🤖 Neuralex бот запущен и готов к работе!")
        print("🤖 Neuralex бот запущен и готов к работе!")
        print("📱 Для остановки нажмите Ctrl+C")
        print("🔍 Если бот не отвечает, запустите: python diagnose_bot.py")
        
        app.run_polling()
        
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        print(f"❌ Критическая ошибка при запуске бота: {e}")
        print("🔍 Запустите диагностику: python diagnose_bot.py")
        raise
    finally:
        # Останавливаем планировщик при завершении
        scheduler.stop()

if __name__ == "__main__":
    main()
