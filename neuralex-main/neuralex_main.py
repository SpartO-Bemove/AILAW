import threading
import logging
import time
from .cache import RedisCache
from langchain.schema import HumanMessage, AIMessage
from .chains import get_rag_chain
from .prompts import SYSTEM_PROMPT, QA_PROMPT

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

class neuralex:
    """
    neuralex is a conversational AI interface that leverages a retrieval-augmented generation (RAG) pipeline 
    to answer user queries based on vector search and LLM responses. It supports Redis-based caching to improve 
    performance and stores session-based chat histories in memory.

    Attributes:
        llm: An instance of the language model to use (e.g., OpenAI, Anthropic, etc.).
        embeddings: Embedding model used for vectorization of text.
        vector_store: A vector store (e.g., Chroma, FAISS) used for semantic retrieval.
        cache: Instance of RedisCache for caching responses and chat histories.

    Args:
        llm (BaseLanguageModel): The LLM to generate responses.
        embeddings (Embeddings): Embedding model used for vector search.
        vector_store (VectorStore): A vector store instance to fetch relevant documents.
        redis_url (str): Redis connection string. Defaults to "redis://localhost:6379/0".

    Methods:
        get_session_history(session_id: str) -> RedisChatMessageHistory:
            Retrieves or initializes the chat history for the given session ID.
        
        conversational(query: str, session_id: str) -> Tuple[str, list]:
            Handles the user query, checks for cached responses, invokes RAG pipeline if necessary,
            updates history, and returns answer and updated messages.
    """
    store = {}
    store_lock = threading.Lock()

    def __init__(self, llm, embeddings, vector_store, redis_url="redis://localhost:6379/0"):
        self.llm = llm
        self.embeddings = embeddings
        self.vector_store = vector_store
        
        try:
            self.cache = RedisCache(redis_url)
            logger.info(f"Redis кэш инициализирован: {redis_url}")
        except Exception as e:
            logger.error(f"Ошибка инициализации Redis кэша: {e}")
            self.cache = None

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

    def conversational(self, query, session_id):
        """
        Handles a query from a user within a session:
        - Uses Redis-based history for retrieval.
        - Returns cached response if available.
        - Otherwise, runs full RAG pipeline and updates history.

        Returns:
            Tuple[str, list]: (LLM answer, updated message list)
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

        try:
            rag_chain = get_rag_chain(self.llm, self.vector_store, SYSTEM_PROMPT, QA_PROMPT)

            chat_history_obj = self.get_session_history(session_id)
            messages = chat_history_obj.messages

            logger.debug(f"Отправляем запрос в RAG цепочку для session_id: {session_id}")
            
            response = rag_chain.invoke(
            {"input": query, "chat_history": messages},
            config={"configurable": {"session_id": session_id}},
        )

            answer = response['answer']

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
            
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса для session_id {session_id}: {e}")
            raise
