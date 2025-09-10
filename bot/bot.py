from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from .config import TOKEN
from .handlers import start, button_handler, handle_user_message

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Для обычных сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
