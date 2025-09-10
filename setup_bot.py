#!/usr/bin/env python3
"""
Скрипт для проверки настройки бота перед запуском
"""

import os
import sys
from dotenv import load_dotenv

def check_environment():
    """Проверяет наличие всех необходимых переменных окружения"""
    load_dotenv()
    
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'OPENAI_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Отсутствуют следующие переменные окружения:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nДобавьте их в файл .env")
        return False
    
    print("✅ Все переменные окружения настроены")
    return True

def check_chroma_db():
    """Проверяет наличие базы данных Chroma"""
    db_path = "chroma_db_legal_bot_part1"
    if os.path.exists(db_path):
        print("✅ База данных Chroma найдена")
        return True
    else:
        print("❌ База данных Chroma не найдена")
        print(f"   Ожидается в: {db_path}")
        print("   Убедитесь, что векторная база данных создана")
        return False

def check_imports():
    """Проверяет возможность импорта всех необходимых модулей"""
    try:
        import telegram
        print("✅ python-telegram-bot установлен")
    except ImportError:
        print("❌ python-telegram-bot не установлен")
        return False
    
    try:
        import langchain
        print("✅ langchain установлен")
    except ImportError:
        print("❌ langchain не установлен")
        return False
    
    try:
        import openai
        print("✅ openai установлен")
    except ImportError:
        print("❌ openai не установлен")
        return False
    
    try:
        import redis
        print("✅ redis установлен")
    except ImportError:
        print("❌ redis не установлен")
        return False
    
    try:
        import chromadb
        print("✅ chromadb установлен")
    except ImportError:
        print("❌ chromadb не установлен")
        return False
    
    return True

def check_bot_structure():
    """Проверяет структуру файлов бота"""
    required_files = [
        'bot/bot.py',
        'bot/handlers.py',
        'bot/keyboards.py',
        'bot/config.py',
        'neuralex-main/neuralex_main.py',
        'neuralex-main/cache.py',
        'neuralex-main/chains.py',
        'neuralex-main/prompts.py',
        'run_bot.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Отсутствуют следующие файлы:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False
    
    print("✅ Все необходимые файлы найдены")
    return True

def main():
    print("🔍 Проверка настройки телеграм-бота neuralex...\n")
    
    checks = [
        check_bot_structure(),
        check_imports(),
        check_environment(),
        check_chroma_db()
    ]
    
    if all(checks):
        print("\n✅ Все проверки пройдены! Бот готов к запуску.")
        print("Запустите бота командой: python run_bot.py")
        print("\n📝 Не забудьте:")
        print("   - Запустить Redis сервер (если используете кэширование)")
        print("   - Проверить токен бота в @BotFather")
    else:
        print("\n❌ Обнаружены проблемы. Исправьте их перед запуском бота.")
        sys.exit(1)

if __name__ == "__main__":
    main()