"""
Расширенная версия neuralex с поддержкой динамической загрузки документов
"""
import logging
import time
import threading
from typing import List, Optional
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from .neuralex_main import neuralex
from .document_loader import DocumentLoader

logger = logging.getLogger(__name__)

class EnhancedNeuralex(neuralex):
    """Расширенная версия neuralex с поддержкой дополнительных документов"""
    
    def __init__(self, llm, embeddings, vector_store, redis_url=None, documents_path="documents"):
        super().__init__(llm, embeddings, vector_store, redis_url)
        
        self.document_loader = DocumentLoader(documents_path)
        self.additional_documents_loaded = False
        self.documents_stats = {}
        
        # Загружаем дополнительные документы при инициализации
        self._load_additional_documents()
    
    def _load_additional_documents(self):
        """Загружает дополнительные документы в векторную базу"""
        try:
            logger.info("🔄 Проверка дополнительных документов...")
            
            # Загружаем документы
            additional_docs = self.document_loader.load_all_documents()
            
            if additional_docs:
                logger.info(f"📚 Найдено {len(additional_docs)} дополнительных фрагментов")
                
                # Добавляем в векторную базу
                self._add_documents_to_vector_store(additional_docs)
                self.additional_documents_loaded = True
                
                # Сохраняем статистику
                self.documents_stats = self.document_loader.get_documents_stats()
                
                logger.info("✅ Дополнительные документы успешно загружены")
            else:
                logger.info("📝 Дополнительные документы не найдены")
                self.documents_stats = self.document_loader.get_documents_stats()
                
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке дополнительных документов: {e}")
            # Не прерываем работу, продолжаем с базовой функциональностью
    
    def _add_documents_to_vector_store(self, documents: List[Document]):
        """Добавляет документы в векторную базу"""
        try:
            if not documents:
                return
            
            # Добавляем документы батчами для лучшей производительности
            batch_size = 50
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                
                # Извлекаем тексты и метаданные
                texts = [doc.page_content for doc in batch]
                metadatas = [doc.metadata for doc in batch]
                
                # Добавляем в Chroma
                self.vector_store.add_texts(texts=texts, metadatas=metadatas)
                
                logger.debug(f"Добавлен батч {i//batch_size + 1}: {len(batch)} документов")
            
            # Сохраняем изменения
            if hasattr(self.vector_store, 'persist'):
                self.vector_store.persist()
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении документов в векторную базу: {e}")
            raise
    
    def reload_documents(self):
        """Перезагружает дополнительные документы"""
        try:
            logger.info("🔄 Перезагрузка дополнительных документов...")
            self._load_additional_documents()
            return True
        except Exception as e:
            logger.error(f"Ошибка при перезагрузке документов: {e}")
            return False
    
    def get_documents_info(self) -> dict:
        """Возвращает информацию о загруженных документах"""
        info = {
            'additional_documents_loaded': self.additional_documents_loaded,
            'stats': self.documents_stats,
            'base_vector_store_available': self.vector_store is not None
        }
        return info
    
    def conversational(self, query, session_id):
        """
        Переопределенный метод с улучшенной обработкой ошибок
        """
        try:
            # Вызываем родительский метод
            return super().conversational(query, session_id)
            
        except Exception as e:
            logger.error(f"Ошибка в conversational для session {session_id}: {e}")
            
            # Если есть проблемы с дополнительными документами, 
            # пробуем работать только с базовой векторной базой
            if self.additional_documents_loaded:
                logger.info("Пробуем ответить используя только базовую векторную базу...")
                try:
                    # Временно отключаем дополнительные документы
                    self.additional_documents_loaded = False
                    result = super().conversational(query, session_id)
                    self.additional_documents_loaded = True  # Восстанавливаем
                    return result
                except Exception as e2:
                    logger.error(f"Ошибка и с базовой векторной базой: {e2}")
            
            # Если ничего не помогло, возвращаем fallback ответ
            fallback_answer = (
                "❌ Извините, произошла техническая ошибка при обработке вашего запроса.\n\n"
                "Возможные причины:\n"
                "• Проблемы с подключением к OpenAI API\n"
                "• Временные неполадки с векторной базой данных\n"
                "• Превышен лимит запросов\n\n"
                "Попробуйте задать вопрос еще раз через несколько минут."
            )
            
            return fallback_answer, []