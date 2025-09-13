#!/usr/bin/env python3
"""
Скрипт для исправления проблем с ChromaDB
"""

import os
import shutil
from dotenv import load_dotenv

def fix_chromadb():
    """Пересоздает базу данных ChromaDB"""
    load_dotenv()
    
    db_path = "chroma_db_legal_bot_part1"
    
    print("🔧 Исправление проблем с ChromaDB...")
    
    # Удаляем старую базу если есть
    if os.path.exists(db_path):
        print(f"🗑️ Удаляем поврежденную базу: {db_path}")
        shutil.rmtree(db_path)
    
    try:
        from langchain_openai import OpenAIEmbeddings
        from langchain_community.vectorstores import Chroma
        
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            print("❌ OPENAI_API_KEY не найден в .env")
            return False
        
        print("🔄 Создание новой базы данных Chroma...")
        
        # Создаем embeddings
        embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        
        # Создаем новую базу данных
        vector_store = Chroma(
            persist_directory=db_path,
            embedding_function=embeddings
        )
        
        # Добавляем тестовые документы для проверки
        test_docs = [
            "Конституция Российской Федерации - основной закон государства, принятый всенародным голосованием 12 декабря 1993 года.",
            "Гражданский кодекс РФ регулирует имущественные и связанные с ними личные неимущественные отношения.",
            "Уголовный кодекс РФ определяет преступления и наказания за их совершение на территории Российской Федерации.",
            "Трудовой кодекс РФ регулирует трудовые отношения между работниками и работодателями.",
            "Семейный кодекс РФ устанавливает условия и порядок вступления в брак, прекращения брака и признания его недействительным."
        ]
        
        print(f"📚 Добавляем {len(test_docs)} тестовых документов...")
        vector_store.add_texts(test_docs)
        
        # Проверяем работу поиска
        results = vector_store.similarity_search("Конституция", k=1)
        if results:
            print("✅ Поиск работает корректно")
        
        print("✅ База данных ChromaDB успешно создана")
        print(f"📊 Добавлено {len(test_docs)} документов")
        print(f"📁 Путь к базе: {db_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при создании базы данных: {e}")
        return False

if __name__ == "__main__":
    success = fix_chromadb()
    if success:
        print("\n🎉 ChromaDB исправлен! Теперь можете запустить бота:")
        print("python run_bot.py")
    else:
        print("\n❌ Не удалось исправить ChromaDB. Проверьте настройки.")