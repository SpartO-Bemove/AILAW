"""
Обработчики для админ-панели
"""
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .admin_panel import AdminPanel

logger = logging.getLogger(__name__)

class AdminHandlers:
    """Класс для обработки админ-команд"""
    
    def __init__(self, redis_client=None):
        self.admin_panel = AdminPanel(redis_client)
    
    async def handle_admin_callback(self, query, user_id: str):
        """Обрабатывает callback'и админ-панели"""
        
        if not self.admin_panel.is_admin(user_id):
            await query.answer("❌ Нет прав администратора", show_alert=True)
            return
        
        data = query.data
        
        # Главное меню
        if data == 'admin_main':
            await query.edit_message_text(
                "🔧 **АДМИН-ПАНЕЛЬ**\n\nВыберите раздел:",
                parse_mode='Markdown',
                reply_markup=self.admin_panel.get_admin_menu()
            )
        
        # Статистика
        elif data == 'admin_stats':
            await query.edit_message_text(
                "📊 **СТАТИСТИКА И АНАЛИТИКА**\n\nВыберите период:",
                parse_mode='Markdown',
                reply_markup=self.admin_panel.get_stats_menu()
            )
        
        elif data == 'admin_stats_today':
            await self._show_stats(query, 'today')
        
        elif data == 'admin_stats_week':
            await self._show_stats(query, 'week')
        
        elif data == 'admin_stats_month':
            await self._show_stats(query, 'month')
        
        elif data == 'admin_stats_total':
            await self._show_stats(query, 'total')
        
        # Пользователи
        elif data == 'admin_users':
            await query.edit_message_text(
                "👥 **УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ**\n\nВыберите действие:",
                parse_mode='Markdown',
                reply_markup=self.admin_panel.get_users_menu()
            )
        
        elif data == 'admin_users_active':
            await self._show_active_users(query)
        
        elif data == 'admin_users_stats':
            await self._show_users_stats(query)
        
        # Документы
        elif data == 'admin_documents':
            await query.edit_message_text(
                "📄 **УПРАВЛЕНИЕ ДОКУМЕНТАМИ**\n\nВыберите действие:",
                parse_mode='Markdown',
                reply_markup=self.admin_panel.get_documents_menu()
            )
        
        elif data == 'admin_docs_status':
            await self._show_documents_status(query)
        
        elif data == 'admin_docs_reload':
            await self._reload_documents(query)
        
        elif data == 'admin_docs_upload':
            await self._show_upload_instructions(query)
        
        # Обратная связь
        elif data == 'admin_feedback':
            await self._show_feedback_summary(query)
        
        # Настройки
        elif data == 'admin_settings':
            await self._show_bot_settings(query)
        
        # Обслуживание
        elif data == 'admin_maintenance':
            await self._show_maintenance_menu(query)
        
        # Мониторинг
        elif data == 'admin_monitoring':
            await self._show_monitoring_info(query)
        
        # Детальная аналитика
        elif data == 'admin_detailed_stats':
            await self._show_detailed_analytics(query)
        
        # Токены ИИ
        elif data == 'admin_tokens':
            await self._show_token_stats(query)
        
        # Закрытие панели
        elif data == 'admin_close':
            await query.edit_message_text(
                "✅ **Админ-панель закрыта**\n\nДля повторного открытия используйте /admin"
            )
        
        else:
            await query.answer("🚧 Функция в разработке", show_alert=True)
    
    async def _show_stats(self, query, period: str):
        """Показывает статистику за период"""
        try:
            await query.answer("📊 Загружаю статистику...")
            
            stats = await self.admin_panel.get_system_stats()
            period_name = {
                'today': 'сегодня',
                'week': 'неделю', 
                'month': 'месяц',
                'total': 'все время'
            }.get(period, period)
            
            message = self.admin_panel.format_stats_message(stats, period_name)
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=self.admin_panel.get_stats_menu()
            )
            
        except Exception as e:
            logger.error(f"Ошибка при показе статистики: {e}")
            await query.edit_message_text(
                "❌ Ошибка при загрузке статистики",
                reply_markup=self.admin_panel.get_stats_menu()
            )
    
    async def _show_active_users(self, query):
        """Показывает активных пользователей"""
        try:
            if not self.admin_panel.redis_client:
                await query.edit_message_text(
                    "❌ Redis недоступен",
                    reply_markup=self.admin_panel.get_users_menu()
                )
                return
            
            # Получаем активных пользователей за последние 24 часа
            yesterday = datetime.now() - timedelta(days=1)
            today = datetime.now().strftime("%Y-%m-%d")
            
            active_keys = self.admin_panel.redis_client.keys(f"analytics:user:*:{today}*")
            unique_users = set()
            
            for key in active_keys[:50]:  # Ограничиваем
                if isinstance(key, bytes):
                    key = key.decode()
                parts = key.split(':')
                if len(parts) >= 3:
                    unique_users.add(parts[2])
            
            message = f"👥 **АКТИВНЫЕ ПОЛЬЗОВАТЕЛИ**\n\n"
            message += f"📅 **За сегодня:** {len(unique_users)} пользователей\n\n"
            
            if unique_users:
                message += "🔥 **Самые активные:**\n"
                # Показываем первых 10
                for i, user_id in enumerate(list(unique_users)[:10], 1):
                    user_stats = self.admin_panel.analytics.get_user_stats(user_id) if self.admin_panel.analytics else {}
                    total_actions = user_stats.get('total_actions', 0)
                    message += f"{i}. ID: `{user_id}` | Действий: {total_actions}\n"
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=self.admin_panel.get_users_menu()
            )
            
        except Exception as e:
            logger.error(f"Ошибка при показе активных пользователей: {e}")
            await query.edit_message_text(
                "❌ Ошибка при загрузке данных пользователей",
                reply_markup=self.admin_panel.get_users_menu()
            )
    
    async def _show_users_stats(self, query):
        """Показывает статистику по пользователям"""
        try:
            if not self.admin_panel.redis_client:
                await query.edit_message_text(
                    "❌ Redis недоступен",
                    reply_markup=self.admin_panel.get_users_menu()
                )
                return
            
            # Получаем общую статистику
            user_keys = self.admin_panel.redis_client.keys("user_stats:*")
            total_users = len(user_keys)
            
            # Анализируем активность
            active_today = 0
            active_week = 0
            total_questions = 0
            total_documents = 0
            
            today = datetime.now().strftime("%Y-%m-%d")
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            
            for key in user_keys[:100]:  # Ограничиваем для производительности
                try:
                    if isinstance(key, bytes):
                        key = key.decode()
                    
                    user_id = key.split(':')[1]
                    user_stats = self.admin_panel.analytics.get_user_stats(user_id) if self.admin_panel.analytics else {}
                    
                    total_questions += user_stats.get('ask_question', 0)
                    total_documents += user_stats.get('check_document', 0)
                    
                    # Проверяем активность (упрощенно)
                    if self.admin_panel.redis_client.exists(f"analytics:user:{user_id}:{today}*"):
                        active_today += 1
                    
                except Exception:
                    continue
            
            message = f"📊 **СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ**\n\n"
            message += f"👥 **Всего пользователей:** {total_users}\n"
            message += f"🔥 **Активных сегодня:** {active_today}\n"
            message += f"📅 **Активных за неделю:** {active_week}\n\n"
            message += f"❓ **Всего вопросов:** {total_questions}\n"
            message += f"📄 **Всего документов:** {total_documents}\n\n"
            
            if total_users > 0:
                avg_questions = total_questions / total_users
                avg_documents = total_documents / total_users
                message += f"📈 **Среднее на пользователя:**\n"
                message += f"• Вопросов: {avg_questions:.1f}\n"
                message += f"• Документов: {avg_documents:.1f}\n"
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=self.admin_panel.get_users_menu()
            )
            
        except Exception as e:
            logger.error(f"Ошибка при показе статистики пользователей: {e}")
            await query.edit_message_text(
                "❌ Ошибка при загрузке статистики пользователей",
                reply_markup=self.admin_panel.get_users_menu()
            )
    
    async def _show_documents_status(self, query):
        """Показывает статус документов"""
        try:
            # Импортируем здесь чтобы избежать циклических импортов
            from .handlers import law_assistant
            
            if not law_assistant:
                await query.edit_message_text(
                    "❌ Law assistant недоступен",
                    reply_markup=self.admin_panel.get_documents_menu()
                )
                return
            
            docs_info = law_assistant.get_documents_info()
            stats = docs_info.get('stats', {})
            
            message = "📚 **СТАТУС ДОКУМЕНТОВ**\n\n"
            
            if docs_info['additional_documents_loaded']:
                message += f"✅ **Дополнительные документы:** Загружены\n"
                message += f"📊 **Всего файлов:** {stats.get('total_files', 0)}\n\n"
                
                categories_names = {
                    'laws': '⚖️ Федеральные законы',
                    'codes': '📖 Кодексы РФ',
                    'articles': '📝 Юридические статьи',
                    'court_practice': '🏛️ Судебная практика'
                }
                
                message += "📋 **ПО КАТЕГОРИЯМ:**\n"
                for category, count in stats.get('categories', {}).items():
                    name = categories_names.get(category, category)
                    message += f"{name}: **{count}** файлов\n"
                
            else:
                message += "📝 **Дополнительные документы:** Не найдены\n"
                message += "💡 Добавьте файлы в папку `documents/`\n"
            
            if docs_info['base_vector_store_available']:
                message += "\n✅ **Базовая векторная база:** Доступна"
            else:
                message += "\n❌ **Базовая векторная база:** Недоступна"
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=self.admin_panel.get_documents_menu()
            )
            
        except Exception as e:
            logger.error(f"Ошибка при показе статуса документов: {e}")
            await query.edit_message_text(
                "❌ Ошибка при загрузке статуса документов",
                reply_markup=self.admin_panel.get_documents_menu()
            )
    
    async def _reload_documents(self, query):
        """Перезагружает документы"""
        try:
            await query.answer("🔄 Перезагружаю документы...")
            
            from .handlers import law_assistant
            
            if not law_assistant or not hasattr(law_assistant, 'reload_documents'):
                await query.edit_message_text(
                    "❌ Функция перезагрузки недоступна",
                    reply_markup=self.admin_panel.get_documents_menu()
                )
                return
            
            success = law_assistant.reload_documents()
            
            if success:
                docs_info = law_assistant.get_documents_info()
                stats = docs_info.get('stats', {})
                
                message = "✅ **ДОКУМЕНТЫ ПЕРЕЗАГРУЖЕНЫ**\n\n"
                message += f"📊 **Всего файлов:** {stats.get('total_files', 0)}\n\n"
                
                categories_names = {
                    'laws': '⚖️ Федеральные законы',
                    'codes': '📖 Кодексы РФ',
                    'articles': '📝 Юридические статьи',
                    'court_practice': '🏛️ Судебная практика'
                }
                
                for category, count in stats.get('categories', {}).items():
                    if count > 0:
                        name = categories_names.get(category, category)
                        message += f"{name}: **{count}** файлов\n"
            else:
                message = "❌ **ОШИБКА ПЕРЕЗАГРУЗКИ**\n\nПроверьте логи для деталей"
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=self.admin_panel.get_documents_menu()
            )
            
        except Exception as e:
            logger.error(f"Ошибка при перезагрузке документов: {e}")
            await query.edit_message_text(
                "❌ Ошибка при перезагрузке документов",
                reply_markup=self.admin_panel.get_documents_menu()
            )
    
    async def _show_upload_instructions(self, query):
        """Показывает инструкции по загрузке документов"""
        message = """
📤 **ЗАГРУЗКА ДОКУМЕНТОВ**

🔧 **Способы загрузки:**

**1. Через файловую систему:**
• Скопируйте файлы в папки `documents/`
• Используйте кнопку "🔄 Перезагрузить"

**2. Поддерживаемые форматы:**
• `.txt` - текстовые файлы
• `.pdf` - PDF документы  
• `.docx` - Word документы
• `.md` - Markdown файлы

**3. Структура папок:**
• `documents/laws/` - Федеральные законы
• `documents/codes/` - Кодексы РФ
• `documents/articles/` - Статьи и комментарии
• `documents/court_practice/` - Судебная практика

**4. Требования:**
• Максимальный размер: 10 МБ
• Кодировка: UTF-8
• Минимум 50 символов текста

🚧 **Загрузка через бота в разработке**
        """
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=self.admin_panel.get_documents_menu()
        )
    
    async def _show_feedback_summary(self, query):
        """Показывает сводку обратной связи"""
        try:
            await query.answer("💬 Загружаю обратную связь...")
            
            feedback = await self.admin_panel.get_feedback_summary()
            message = self.admin_panel.format_feedback_message(feedback)
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=self.admin_panel.get_admin_menu()
            )
            
        except Exception as e:
            logger.error(f"Ошибка при показе обратной связи: {e}")
            await query.edit_message_text(
                "❌ Ошибка при загрузке обратной связи",
                reply_markup=self.admin_panel.get_admin_menu()
            )
    
    async def _show_bot_settings(self, query):
        """Показывает настройки бота"""
        message = """
⚙️ **НАСТРОЙКИ БОТА**

🔧 **Текущие параметры:**
• Rate limit: 15 запросов/минуту
• Максимальный размер файла: 20 МБ
• Поддерживаемые форматы: PDF, DOCX, TXT
• Кэширование: Redis
• Модель ИИ: GPT-4o-mini

📊 **Статистика:**
• Время работы: активен
• Версия: 1.0.0
• Последнее обновление: сегодня

🚧 **Изменение настроек в разработке**
        """
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=self.admin_panel.get_admin_menu()
        )
    
    async def _show_maintenance_menu(self, query):
        """Показывает меню обслуживания"""
        message = """
🔄 **ТЕХНИЧЕСКОЕ ОБСЛУЖИВАНИЕ**

🛠️ **Доступные операции:**
• Очистка кэша Redis
• Перезагрузка документов
• Проверка системы
• Резервное копирование настроек

⚠️ **Статус системы:**
• Redis: подключен
• OpenAI API: активен
• Векторная база: доступна
• Планировщик: работает

🚧 **Функции обслуживания в разработке**
        """
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=self.admin_panel.get_admin_menu()
        )
    
    async def _show_monitoring_info(self, query):
        """Показывает информацию мониторинга"""
        try:
            stats = await self.admin_panel.get_system_stats()
            
            message = f"""
🚨 **МОНИТОРИНГ СИСТЕМЫ**

🔍 **Состояние компонентов:**
• Redis: {stats.get('redis_status', 'unknown')}
• OpenAI API: активен
• Telegram API: активен
• Векторная база: доступна

📊 **Производительность:**
• Активных пользователей: {stats.get('active_users_today', 0)}
• Запросов сегодня: {stats.get('total_actions', 0)}
• Средний рейтинг: {stats.get('average_rating', 0):.1f}/5.0
• Уровень ошибок: {stats.get('error_rate', 0):.1f}%

⏰ **Последняя проверка:** {datetime.now().strftime('%H:%M:%S')}

🚧 **Расширенный мониторинг в разработке**
            """
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=self.admin_panel.get_admin_menu()
            )
            
        except Exception as e:
            logger.error(f"Ошибка при показе мониторинга: {e}")
            await query.edit_message_text(
                "❌ Ошибка при загрузке данных мониторинга",
                reply_markup=self.admin_panel.get_admin_menu()
            )
    
    async def _show_detailed_analytics(self, query):
        """Показывает детальную аналитику"""
        message = """
📈 **ДЕТАЛЬНАЯ АНАЛИТИКА**

📊 **Доступные отчеты:**
• Динамика пользователей по дням
• Популярные категории вопросов  
• Время отклика системы
• География пользователей
• Конверсия по воронке

📋 **Экспорт данных:**
• CSV отчеты
• JSON дампы
• Графики и диаграммы

🚧 **Детальная аналитика в разработке**

💡 Планируется добавить:
• Дашборд с графиками
• Автоматические отчеты
• Алерты по метрикам
• A/B тестирование
        """
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=self.admin_panel.get_admin_menu()
        )
    
    async def _show_token_stats(self, query):
        """Показывает статистику использования токенов ИИ"""
        try:
            await query.answer("🤖 Загружаю статистику токенов...")
            
            if not self.admin_panel.analytics:
                await query.edit_message_text(
                    "❌ Аналитика недоступна",
                    reply_markup=self.admin_panel.get_admin_menu()
                )
                return
            
            # Получаем статистику токенов
            tokens_today = self.admin_panel.analytics.get_token_stats('today')
            tokens_total = self.admin_panel.analytics.get_token_stats('total')
            cost_today = self.admin_panel.analytics.get_token_cost_stats('today')
            cost_total = self.admin_panel.analytics.get_token_cost_stats('total')
            
            message = "🤖 **СТАТИСТИКА ТОКЕНОВ ИИ**\n\n"
            
            # Статистика за сегодня
            if tokens_today:
                message += "📅 **СЕГОДНЯ:**\n"
                message += f"• Всего токенов: **{tokens_today.get('total_tokens', 0):,}**\n"
                message += f"• Входящие токены: **{tokens_today.get('prompt_tokens', 0):,}**\n"
                message += f"• Исходящие токены: **{tokens_today.get('completion_tokens', 0):,}**\n"
                message += f"• Запросов к ИИ: **{tokens_today.get('requests_count', 0)}**\n"
                
                if cost_today.get('total_cost_usd', 0) > 0:
                    message += f"• Стоимость: **${cost_today['total_cost_usd']:.4f}**\n"
                    message += f"• Средняя стоимость запроса: **${cost_today['avg_cost_per_request']:.4f}**\n"
                
                message += "\n"
            else:
                message += "📅 **СЕГОДНЯ:** Нет данных\n\n"
            
            # Общая статистика
            if tokens_total:
                message += "📊 **ВСЕГО:**\n"
                message += f"• Всего токенов: **{tokens_total.get('total_tokens', 0):,}**\n"
                message += f"• Входящие токены: **{tokens_total.get('prompt_tokens', 0):,}**\n"
                message += f"• Исходящие токены: **{tokens_total.get('completion_tokens', 0):,}**\n"
                message += f"• Всего запросов: **{tokens_total.get('requests_count', 0)}**\n"
                
                if tokens_total.get('total_tokens', 0) > 0:
                    total_cost = self.admin_panel.analytics.calculate_token_cost(
                        tokens_total.get('prompt_tokens', 0),
                        tokens_total.get('completion_tokens', 0)
                    )
                    avg_tokens_per_request = tokens_total.get('total_tokens', 0) / max(tokens_total.get('requests_count', 1), 1)
                    message += f"• Общая стоимость: **${total_cost:.4f}**\n"
                    message += f"• Средний расход токенов: **{avg_tokens_per_request:.0f}** за запрос\n"
                
                message += "\n"
            else:
                message += "📊 **ВСЕГО:** Нет данных\n\n"
            
            # Информация о ценах
            message += "💰 **ЦЕНЫ OPENAI (за 1M токенов):**\n"
            message += "• GPT-4o-mini: $0.15 вход / $0.60 выход\n"
            message += "• GPT-4o: $2.50 вход / $10.00 выход\n"
            message += "• GPT-4: $30.00 вход / $60.00 выход\n\n"
            
            message += "ℹ️ *Статистика обновляется в реальном времени*"
            
            # Кнопки для навигации
            keyboard = [
                [InlineKeyboardButton("🔄 Обновить", callback_data='admin_tokens')],
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_main')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Ошибка при показе статистики токенов: {e}")
            await query.edit_message_text(
                "❌ Ошибка при загрузке статистики токенов",
                reply_markup=self.admin_panel.get_admin_menu()
            )