import redis
import hashlib
import logging
from langchain_community.chat_message_histories import RedisChatMessageHistory

logger = logging.getLogger(__name__)

class RedisCache:
    """
    Оптимизированный кэш для LLM ответов с TTL
    """
    
    def __init__(self, redis_client=None, redis_url=None):
        self.redis_client = redis_client
        self.redis_url = redis_url
        # Локальный кэш для очень быстрого доступа
        self.local_cache = {}
        self.local_cache_size = 100

    def make_cache_key(self, query, session_id):
        # Упрощенный ключ для быстрого доступа
        key_raw = f"{session_id}:{query[:100]}"  # Ограничиваем длину
        return "llm_cache:" + hashlib.sha256(key_raw.encode()).hexdigest()

    def get(self, key):
        # Сначала проверяем локальный кэш
        if key in self.local_cache:
            return self.local_cache[key]
            
        if not self.redis_client:
            return None
        try:
            value = self.redis_client.get(key)
            # Сохраняем в локальный кэш
            if value and len(self.local_cache) < self.local_cache_size:
                self.local_cache[key] = value
            return value if value else None
        except Exception as e:
            logger.error(f"Ошибка при получении значения из кэша для ключа {key}: {e}")
            return None

    def set(self, key: str, value: str, ttl: int = None) -> None:
        # Сохраняем в локальный кэш
        if len(self.local_cache) < self.local_cache_size:
            self.local_cache[key] = value
            
        if not self.redis_client:
            return
        try:
            # Устанавливаем TTL по умолчанию для экономии памяти
            ttl = ttl or 3600  # 1 час по умолчанию
            self.redis_client.setex(key, ttl, value)
            logger.debug(f"Значение сохранено в кэш для ключа: {key}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении значения в кэш для ключа {key}: {e}")

    def get_chat_history(self, session_id):
        if not self.redis_client:
            # Fallback на локальную историю
            from langchain.memory import ChatMessageHistory
            return ChatMessageHistory()
        try:
            return RedisChatMessageHistory(session_id=session_id, url=self.redis_url or "redis://localhost:6379/0")
        except Exception as e:
            logger.error(f"Ошибка при создании истории чата для session_id {session_id}: {e}")
