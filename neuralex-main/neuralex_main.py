import threading
import logging
import time
import asyncio
from openai import OpenAI
from cache import RedisCache
from langchain.schema import HumanMessage, AIMessage
from chains import get_rag_chain
from prompts import SYSTEM_PROMPT, QA_PROMPT

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

class neuralex:
    """
    Conversational AI для юридических консультаций с RAG pipeline
    """
    store = {}
    store_lock = threading.Lock()

    def __init__(self, llm, embeddings, vector_store, redis_url=None):
        self.llm = llm
        self.embeddings = embeddings
        self.vector_store = vector_store
        
        # Кэш для быстрых ответов
        self.quick_answers_cache = {}
        self.last_context_cache = {}
        
        # Инициализируем кэш с внешним Redis клиентом
        redis_client = None
        if redis_url:
            try:
                import redis
                redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
                redis_client.ping()
                logger.info(f"Redis кэш инициализирован: {redis_url}")
            except Exception as e:
                logger.error(f"Ошибка инициализации Redis кэша: {e}")
                redis_client = None
        
        self.cache = RedisCache(redis_client)

    def is_simple_question(self, query):
        """Определяет, является ли вопрос простым для быстрого ответа"""
        simple_keywords = [
            'что такое', 'кто такой', 'как называется', 'определение',
            'сколько', 'когда', 'где', 'какой срок', 'какая статья'
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in simple_keywords)

    def get_quick_context(self, query):
        """Быстрый поиск контекста без сложной RAG цепочки"""
        try:
            # Простой similarity search без history-aware retriever
            docs = self.vector_store.similarity_search(
                query, 
                k=3,  # Меньше документов = быстрее
                score_threshold=0.4
            )
            return "\n".join([doc.page_content[:500] for doc in docs])  # Ограничиваем размер
        except Exception as e:
            logger.error(f"Ошибка быстрого поиска: {e}")
            return ""

    def get_session_history(self, session_id):
        with neuralex.store_lock:
            if session_id not in neuralex.store:
                if self.cache:
                    neuralex.store[session_id] = self.cache.get_chat_history(session_id)
                    logger.info(f"Создана новая история чата для session_id: {session_id}")
                else:
                    # Fallback без Redis
                    from langchain.memory import ChatMessageHistory
                    neuralex.store[session_id] = ChatMessageHistory()
                    logger.warning(f"Создана локальная история чата для session_id: {session_id} (Redis недоступен)")
            else:
                logger.debug(f"Используется существующая история чата для session_id: {session_id}")
        return neuralex.store[session_id]

    async def conversational_async(self, query, session_id):
        """Асинхронная версия conversational для ускорения"""
        return self.conversational(query, session_id)

    def conversational(self, query, session_id, use_fast_mode=True):
        """
        Обрабатывает запрос с оптимизацией скорости:
        - Проверяет кэш
        - Для простых вопросов использует быстрый режим
        - Для сложных - полную RAG цепочку

        Returns:
            Tuple[str, list]: (ответ ИИ, обновленная история)
        """
        start_time = time.time()
        
        # Проверяем кэш только если он доступен
        cached_answer = None
        if self.cache:
            try:
                cache_key = self.cache.make_cache_key(query, session_id)
                cached_answer = self.cache.get(cache_key)
                if cached_answer:
                    logger.info(f"Попадание в кэш для ключа: {cache_key}")
                    chat_history = self.get_session_history(session_id).messages
                    return cached_answer, chat_history
            except Exception as e:
                logger.error(f"Ошибка при работе с кэшем: {e}")

        logger.info(f"Промах кэша. Генерируем новый ответ для session_id: {session_id}")

        # Определяем режим обработки
        is_simple = self.is_simple_question(query) if use_fast_mode else False
        
        try:
            chat_history_obj = self.get_session_history(session_id)
            messages = chat_history_obj.messages

            if is_simple and len(messages) < 4:  # Быстрый режим для простых вопросов
                logger.info(f"Используем быстрый режим для session_id: {session_id}")
                
                # Быстрый поиск контекста
                context = self.get_quick_context(query)
                
                # Простой промпт без сложной цепочки
                simple_prompt = f"""
{SYSTEM_PROMPT}

Контекст: {context}

Вопрос: {query}

Дай краткий, но полный ответ на основе контекста. Используй структуру:

🎯 **КРАТКИЙ ОТВЕТ:**
[Основная суть в 1-2 предложениях]

📋 **ПОДРОБНО:**
[Развернутое объяснение]

⚖️ **ПРАВОВАЯ БАЗА:**
[Конкретные статьи и законы если есть в контексте]
"""
                
                # Прямой вызов LLM без RAG цепочки
                response = self.llm.invoke([HumanMessage(content=simple_prompt)])
                answer = response.content
                
            else:  # Полная RAG цепочка для сложных вопросов
                logger.info(f"Используем полную RAG цепочку для session_id: {session_id}")
                rag_chain = get_rag_chain(self.llm, self.vector_store, SYSTEM_PROMPT, QA_PROMPT)
                
                response = rag_chain.invoke(
                    {"input": query, "chat_history": messages}
                )
                answer = response['answer']

            logger.debug(f"Ответ получен для session_id: {session_id}")

            # Обновляем историю чата
            chat_history_obj.add_user_message(query)
            chat_history_obj.add_ai_message(answer)

            # Кэшируем ответ, если кэш доступен
            if self.cache:
                try:
                    self.cache.set(cache_key, answer)
                    logger.debug(f"Ответ закэширован для ключа: {cache_key}")
                except Exception as e:
                    logger.error(f"Ошибка при кэшировании ответа: {e}")

            processing_time = time.time() - start_time
            logger.info(f"Запрос обработан за {processing_time:.2f} секунд для session_id: {session_id}")
            
            return answer, chat_history_obj.messages
            
        except Exception as openai_error:
            # Проверяем, является ли это ошибкой OpenAI
            error_str = str(openai_error).lower()
            if any(keyword in error_str for keyword in ['openai', 'api key', 'rate limit', 'quota', 'authentication']):
                logger.error(f"OpenAI API ошибка для session_id {session_id}: {openai_error}")
                # Пробрасываем ошибку OpenAI выше для специальной обработки
                raise openai_error
            else:
                logger.error(f"Общая ошибка при обработке запроса для session_id {session_id}: {openai_error}")
                raise
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса для session_id {session_id}: {e}")
            raise
