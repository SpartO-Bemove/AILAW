"""
Модуль для аналитики и статистики использования бота
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import redis
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)

class BotAnalytics:
    """Класс для сбора и анализа статистики использования бота"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        
    def log_user_action(self, user_id: str, action: str, metadata: Dict = None):
        """Логирует действие пользователя"""
        if not self.redis_client:
            return
            
        try:
            timestamp = datetime.now().isoformat()
            event = {
                'user_id': user_id,
                'action': action,
                'timestamp': timestamp,
                'metadata': metadata or {}
            }
            
            # Сохраняем в Redis с TTL 30 дней
            key = f"analytics:user:{user_id}:{timestamp}"
            self.redis_client.setex(key, 30 * 24 * 3600, json.dumps(event))
            
            # Обновляем счетчики
            self._update_counters(user_id, action)
            
        except Exception as e:
            logger.error(f"Ошибка при логировании действия: {e}")
    
    def _update_counters(self, user_id: str, action: str):
        """Обновляет счетчики действий"""
        try:
            # Общий счетчик действий пользователя
            self.redis_client.hincrby(f"user_stats:{user_id}", action, 1)
            self.redis_client.hincrby(f"user_stats:{user_id}", "total_actions", 1)
            
            # Глобальные счетчики
            today = datetime.now().strftime("%Y-%m-%d")
            self.redis_client.hincrby(f"daily_stats:{today}", action, 1)
            self.redis_client.hincrby(f"daily_stats:{today}", "total_actions", 1)
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении счетчиков: {e}")
    
    def get_user_stats(self, user_id: str) -> Dict:
        """Получает статистику пользователя"""
        if not self.redis_client:
            return {}
            
        try:
            stats = self.redis_client.hgetall(f"user_stats:{user_id}")
            return {k.decode() if isinstance(k, bytes) else k: 
                   int(v.decode() if isinstance(v, bytes) else v) 
                   for k, v in stats.items()}
        except Exception as e:
            logger.error(f"Ошибка при получении статистики пользователя: {e}")
            return {}
    
    def get_daily_stats(self, date: str = None) -> Dict:
        """Получает статистику за день"""
        if not self.redis_client:
            return {}
            
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
            
        try:
            stats = self.redis_client.hgetall(f"daily_stats:{date}")
            return {k.decode() if isinstance(k, bytes) else k: 
                   int(v.decode() if isinstance(v, bytes) else v) 
                   for k, v in stats.items()}
        except Exception as e:
            logger.error(f"Ошибка при получении дневной статистики: {e}")
            return {}
    
    def log_question_rating(self, user_id: str, question: str, rating: int):
        """Логирует оценку ответа на вопрос"""
        if not self.redis_client:
            return
            
        try:
            rating_data = {
                'user_id': user_id,
                'question': question[:200],  # Ограничиваем длину
                'rating': rating,
                'timestamp': datetime.now().isoformat()
            }
            
            key = f"ratings:{user_id}:{datetime.now().timestamp()}"
            self.redis_client.setex(key, 30 * 24 * 3600, json.dumps(rating_data))
            
            # Обновляем средний рейтинг
            self._update_average_rating(rating)
            
        except Exception as e:
            logger.error(f"Ошибка при логировании оценки: {e}")
    
    def _update_average_rating(self, rating: int):
        """Обновляет средний рейтинг"""
        try:
            # Используем скользящее среднее
            current_avg = float(self.redis_client.get("avg_rating") or 0)
            current_count = int(self.redis_client.get("rating_count") or 0)
            
            new_count = current_count + 1
            new_avg = (current_avg * current_count + rating) / new_count
            
            self.redis_client.set("avg_rating", new_avg)
            self.redis_client.set("rating_count", new_count)
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении среднего рейтинга: {e}")
    
    def get_average_rating(self) -> float:
        """Получает средний рейтинг"""
        if not self.redis_client:
            return 0.0
            
        try:
            return float(self.redis_client.get("avg_rating") or 0)
        except Exception as e:
            logger.error(f"Ошибка при получении среднего рейтинга: {e}")
            return 0.0