"""
Расширенная версия neuralex с поддержкой динамической загрузки документов
"""
import logging
import logging
import time
import threading
from typing import List, Optional
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from neuralex_main import neuralex
from document_loader import DocumentLoader
from qa_knowledge_base import QAKnowledgeBase

logger = logging.getLogger(__name__)

class EnhancedNeuralex(neuralex):
    """Расширенная версия neuralex с поддержкой дополнительных документов"""
    
    def __init__(self, llm, embeddings, vector_store, redis_url=None, documents_path="documents"):
        super().__init__(llm, embeddings, vector_store, redis_url)
        
        self.document_loader = DocumentLoader(documents_path)
        self.additional_documents_loaded = False
        self.documents_stats = {}
        
        # Инициализируем базу знаний QA
        try:
            self.qa_knowledge = QAKnowledgeBase(
                embeddings=embeddings,
                redis_client=self.cache.redis_client if self.cache else None,
                persist_directory="qa_knowledge_base"
            )
            logger.info("✅ QA Knowledge Base инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации QA Knowledge Base: {e}")
            self.qa_knowledge = None
        
        # Загружаем дополнительные документы при инициализации
        self._load_additional_documents()
    
    def _load_additional_documents(self):
        """Загружает дополнительные документы в векторную базу"""
        try:
            logger.info("🔄 Проверка дополнительных документов...")
            
            # Проверяем, нужно ли перезагружать документы
            if self._should_skip_loading():
                logger.info("⚡ Документы уже загружены, пропускаем векторизацию")
                self.additional_documents_loaded = True
                self.documents_stats = self.document_loader.get_documents_stats()
                return
            
            # Загружаем документы
            additional_docs = self.document_loader.load_all_documents()
            
            if additional_docs:
                logger.info(f"📚 Найдено {len(additional_docs)} дополнительных фрагментов")
                
                # Добавляем в векторную базу
                self._add_documents_to_vector_store(additional_docs)
                self.additional_documents_loaded = True
                
                # Сохраняем статистику
                self.documents_stats = self.document_loader.get_documents_stats()
                
                # Сохраняем метку о загрузке
                self._save_loading_marker()
                
                logger.info("✅ Дополнительные документы успешно загружены")
            else:
                logger.info("📝 Дополнительные документы не найдены")
                self.documents_stats = self.document_loader.get_documents_stats()
                
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке дополнительных документов: {e}")
            # Не прерываем работу, продолжаем с базовой функциональностью
    
    def _should_skip_loading(self) -> bool:
        """Проверяет, нужно ли пропустить загрузку документов"""
        try:
            import os
            import json
            
            marker_file = "documents/.loaded_marker"
            if not os.path.exists(marker_file):
                return False
            
            # Читаем информацию о последней загрузке
            with open(marker_file, 'r') as f:
                marker_data = json.load(f)
            
            # Проверяем, изменились ли файлы
            current_stats = self.document_loader.get_documents_stats()
            if marker_data.get('stats') != current_stats:
                return False
            
            # Проверяем, существует ли векторная база
            if not self.vector_store or not hasattr(self.vector_store, '_collection'):
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Ошибка при проверке маркера загрузки: {e}")
            return False
    
    def _save_loading_marker(self):
        """Сохраняет маркер о завершенной загрузке"""
        try:
            import os
            import json
            from datetime import datetime
            
            marker_data = {
                'loaded_at': datetime.now().isoformat(),
                'stats': self.documents_stats
            }
            
            os.makedirs("documents", exist_ok=True)
            with open("documents/.loaded_marker", 'w') as f:
                json.dump(marker_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Ошибка при сохранении маркера загрузки: {e}")
    
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
        Переопределенный метод с поддержкой QA Knowledge Base
        """
        start_time = time.time()
        
        # 1. Сначала ищем в базе знаний
        if self.qa_knowledge:
            try:
                cached_qa = self.qa_knowledge.find_similar_qa(
                    query, 
                    similarity_threshold=0.85,
                    min_rating=4.0
                )
                
                if cached_qa:
                    logger.info(f"🎯 Найден похожий вопрос в базе знаний (рейтинг: {cached_qa.rating:.1f})")
                    
                    # Обновляем историю чата
                    chat_history_obj = self.get_session_history(session_id)
                    chat_history_obj.add_user_message(query)
                    chat_history_obj.add_ai_message(cached_qa.answer)
                    
                    processing_time = time.time() - start_time
                    logger.info(f"⚡ Ответ из базы знаний за {processing_time:.2f} секунд")
                    
                    return cached_qa.answer, chat_history_obj.messages
                    
            except Exception as e:
                logger.error(f"Ошибка при поиске в базе знаний: {e}")
        
        # 2. Если не найдено в базе знаний - генерируем новый ответ
        try:
            logger.info("🤖 Генерируем новый ответ через RAG")
            answer, chat_history = super().conversational(query, session_id)
            
            # 3. Сохраняем новую пару в базу знаний
            if self.qa_knowledge and answer:
                try:
                    # Извлекаем источники из ответа (упрощенно)
                    sources = self._extract_sources_from_answer(answer)
                    
                    qa_id = self.qa_knowledge.save_qa_pair(
                        question=query,
                        answer=answer,
                        sources=sources,
                        session_id=session_id,
                        initial_rating=3.5  # Нейтральный начальный рейтинг
                    )
                    
                    if qa_id:
                        logger.info(f"💾 QA пара сохранена в базу знаний: {qa_id}")
                        
                        # Сохраняем ID последнего ответа для возможной оценки
                        if self.cache and self.cache.redis_client:
                            try:
                                self.cache.redis_client.setex(
                                    f"last_qa_id:{session_id}",
                                    3600,  # TTL 1 час
                                    qa_id
                                )
                            except Exception:
                                pass
                                
                except Exception as e:
                    logger.error(f"Ошибка при сохранении QA пары: {e}")
            
            processing_time = time.time() - start_time
            logger.info(f"🎯 Новый ответ сгенерирован за {processing_time:.2f} секунд")
            
            return answer, chat_history
            
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
    
    def _extract_sources_from_answer(self, answer: str) -> List[str]:
        """Извлекает источники из ответа (упрощенная версия)"""
        sources = []
        
        # Ищем упоминания статей и кодексов
        import re
        
        # Паттерны для поиска правовых источников
        patterns = [
            r'[Сс]татья\s+\d+[а-я]*\s+[А-Я]{1,3}\s+РФ',  # Статья 80 ТК РФ
            r'[А-Я]{1,3}\s+РФ',  # ТК РФ, ГК РФ и т.д.
            r'[Фф]едеральный\s+закон[^.]*',  # Федеральный закон...
            r'[Кк]онституция\s+РФ',  # Конституция РФ
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, answer)
            sources.extend(matches)
        
        # Убираем дубликаты и ограничиваем количество
        sources = list(set(sources))[:5]
        
        return sources
    
    def rate_last_answer(self, session_id: str, rating: int) -> bool:
        """
        Оценивает последний ответ пользователя
        
        Args:
            session_id: ID сессии пользователя
            rating: Оценка от 1 до 5
            
        Returns:
            True если оценка сохранена успешно
        """
        if not self.qa_knowledge or not self.cache or not self.cache.redis_client:
            return False
        
        try:
            # Получаем ID последнего ответа
            qa_id = self.cache.redis_client.get(f"last_qa_id:{session_id}")
            if not qa_id:
                logger.warning(f"Не найден ID последнего ответа для session {session_id}")
                return False
            
            # Обновляем рейтинг
            success = self.qa_knowledge.update_rating(qa_id, rating)
            
            if success:
                logger.info(f"✅ Рейтинг {rating} сохранен для QA {qa_id}")
                
                # Удаляем ID после оценки
                self.cache.redis_client.delete(f"last_qa_id:{session_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"Ошибка при оценке ответа: {e}")
            return False
    
    def get_qa_stats(self) -> dict:
        """Возвращает статистику базы знаний"""
        if not self.qa_knowledge:
            return {}
        
        try:
            return self.qa_knowledge.get_stats()
        except Exception as e:
            logger.error(f"Ошибка при получении статистики QA: {e}")
            return {}
    
    def get_popular_questions(self, limit: int = 10) -> List:
        """Возвращает популярные вопросы"""
        if not self.qa_knowledge:
            return []
        
        try:
            return self.qa_knowledge.get_popular_questions(limit)
        except Exception as e:
            logger.error(f"Ошибка при получении популярных вопросов: {e}")
            return []