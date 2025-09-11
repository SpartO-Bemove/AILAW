"""
Менеджер состояний пользователей
"""
import logging
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class StateManager:
    """Менеджер для управления состояниями пользователей"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self._local_states = {}  # Fallback для локального хранения
        self._last_answers = {}  # Хранение последних ответов для оценки
    
    def set_user_state(self, user_id: str, state: str):
        """Устанавливает состояние пользователя"""
        try:
            if self.redis_client:
                self.redis_client.setex(f"user_state:{user_id}", 3600, state)  # TTL 1 час
            else:
                self._local_states[user_id] = state
            logger.debug(f"Состояние пользователя {user_id} установлено: {state}")
        except Exception as e:
            logger.error(f"Ошибка при установке состояния пользователя {user_id}: {e}")
            self._local_states[user_id] = state
    
    def get_user_state(self, user_id: str) -> Optional[str]:
        """Получает состояние пользователя"""
        try:
            if self.redis_client:
                state = self.redis_client.get(f"user_state:{user_id}")
                return state
            else:
                return self._local_states.get(user_id)
        except Exception as e:
            logger.error(f"Ошибка при получении состояния пользователя {user_id}: {e}")
            return self._local_states.get(user_id)
    
    def clear_user_state(self, user_id: str):
        """Очищает состояние пользователя"""
        try:
            if self.redis_client:
                self.redis_client.delete(f"user_state:{user_id}")
            if user_id in self._local_states:
                del self._local_states[user_id]
            logger.debug(f"Состояние пользователя {user_id} очищено")
        except Exception as e:
            logger.error(f"Ошибка при очистке состояния пользователя {user_id}: {e}")
    
    def save_last_answer(self, user_id: str, question: str, answer: str):
        """Сохраняет последний ответ для возможной оценки"""
        answer_data = {
            'question': question,
            'answer': answer,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            if self.redis_client:
                import json
                self.redis_client.setex(
                    f"last_answer:{user_id}", 
                    3600,  # TTL 1 час
                    json.dumps(answer_data, ensure_ascii=False)
                )
            else:
                self._last_answers[user_id] = answer_data
            logger.debug(f"Последний ответ сохранен для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении ответа для пользователя {user_id}: {e}")
            self._last_answers[user_id] = answer_data
    
    def get_last_answer(self, user_id: str) -> Optional[Dict]:
        """Получает последний ответ пользователя"""
        try:
            if self.redis_client:
                import json
                data = self.redis_client.get(f"last_answer:{user_id}")
                if data:
                    return json.loads(data)
            else:
                return self._last_answers.get(user_id)
        except Exception as e:
            logger.error(f"Ошибка при получении последнего ответа пользователя {user_id}: {e}")
            return self._last_answers.get(user_id)
    
    def clear_last_answer(self, user_id: str):
        """Удаляет последний ответ пользователя"""
        try:
            if self.redis_client:
                self.redis_client.delete(f"last_answer:{user_id}")
            if user_id in self._last_answers:
                del self._last_answers[user_id]
            logger.debug(f"Последний ответ удален для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при удалении последнего ответа пользователя {user_id}: {e}")