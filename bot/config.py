import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Получаем токен бота
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Проверяем обязательные переменные
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения. Добавьте его в файл .env")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY не найден в переменных окружения. Добавьте его в файл .env")

# Проверяем формат токенов
if TOKEN and not TOKEN.startswith(('1', '2', '5', '6', '7')):
    logging.warning("TELEGRAM_BOT_TOKEN имеет подозрительный формат")
# Настройки бота
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 МБ
ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt']
CHROMA_DB_PATH = "chroma_db_legal_bot_part1"

# ID администратора для получения уведомлений (замените на ваш Telegram ID)
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

# Настройки уведомлений
ENABLE_ADMIN_NOTIFICATIONS = os.getenv('ENABLE_ADMIN_NOTIFICATIONS', 'true').lower() == 'true'

if OPENAI_API_KEY and not OPENAI_API_KEY.startswith('sk-'):
    logging.warning("OPENAI_API_KEY должен начинаться с 'sk-'")

logging.info("Конфигурация бота загружена успешно")