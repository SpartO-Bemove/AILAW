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

# Настройки бота
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 МБ
ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt']
CHROMA_DB_PATH = "chroma_db_legal_bot_part1"

logging.info("Конфигурация бота загружена успешно")