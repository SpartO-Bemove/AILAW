from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from .config import TOKEN
from .handlers import start, button_handler, handle_user_message

def main():
    """Основная функция запуска бота"""
    app = Application.builder().token(TOKEN).build()

    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))

    print("🤖 Neuralex бот запущен и готов к работе!")
    print("📱 Для остановки нажмите Ctrl+C")
    app.run_polling()

if __name__ == "__main__":
    main()
