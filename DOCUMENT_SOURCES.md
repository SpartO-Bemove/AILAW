# 📚 Источники документов в системе Neuralex

## 🔍 **Откуда берутся документы для ответов?**

### **1. 📁 Основная векторная база: `chroma_db_legal_bot_part1/`**

Это **главный источник** юридических знаний бота. В этой папке хранится:

```
chroma_db_legal_bot_part1/
├── chroma.sqlite3          # База данных векторов
├── index/                  # Индексы для поиска
└── metadata/              # Метаданные документов
```

**Что содержит:**
- ✅ Конституция РФ
- ✅ Гражданский кодекс РФ (ГК РФ)
- ✅ Уголовный кодекс РФ (УК РФ)
- ✅ Трудовой кодекс РФ (ТК РФ)
- ✅ Семейный кодекс РФ (СК РФ)
- ✅ Налоговый кодекс РФ (НК РФ)
- ✅ КоАП РФ
- ✅ Жилищный кодекс РФ
- ✅ И другие основные кодексы

### **2. 📂 Дополнительные документы: `documents/`**

Система также сканирует папку `documents/` для дополнительных материалов:

```
documents/
├── laws/                   # Федеральные законы
│   └── example_law.txt
├── codes/                  # Дополнительные кодексы
│   └── example_code.txt
├── articles/               # Юридические статьи
│   └── example_article.txt
└── court_practice/         # Судебная практика
    └── example_practice.txt
```

## 🔧 **Как это настроено в коде:**

### **В файле `neuralex-main/enhanced_neuralex.py`:**

```python
class EnhancedNeuralex(neuralex):
    def __init__(self, llm, embeddings, vector_store, redis_url=None, documents_path="documents"):
        super().__init__(llm, embeddings, vector_store, redis_url)
        
        # Загружаем дополнительные документы
        self.document_loader = DocumentLoader(documents_path)
        self._load_additional_documents()
    
    def _load_additional_documents(self):
        # Сканируем папку documents/
        additional_docs = self.document_loader.load_all_documents()
        
        if additional_docs:
            # Добавляем в векторную базу
            self._add_documents_to_vector_store(additional_docs)
```

### **В файле `bot/handlers.py`:**

```python
# Инициализация векторной базы
vector_store = Chroma(
    persist_directory="chroma_db_legal_bot_part1",  # ← ОСНОВНАЯ БАЗА
    embedding_function=embeddings
)

# Создаем enhanced neuralex с дополнительными документами
law_assistant = EnhancedNeuralex(
    llm, embeddings, vector_store, 
    redis_url, "documents"  # ← ДОПОЛНИТЕЛЬНЫЕ ДОКУМЕНТЫ
)
```

## 📊 **Статус документов в системе:**

### **✅ Что УЖЕ настроено:**

1. **Основная база `chroma_db_legal_bot_part1/`:**
   - Содержит основные кодексы РФ
   - Готова к использованию
   - Векторизована и индексирована

2. **Система загрузки дополнительных документов:**
   - Автоматически сканирует папку `documents/`
   - Поддерживает PDF, DOCX, TXT, MD
   - Добавляет в векторную базу при запуске

### **📝 Что можно ДОБАВИТЬ:**

В папку `documents/` можно добавить:
- Новые федеральные законы
- Постановления правительства
- Судебную практику
- Комментарии к кодексам
- Разъяснения Верховного Суда

## 🔍 **Как проверить, что загружено:**

### **1. Через админ-панель бота:**
```
/admin → 📄 Документы → 📚 Статус документов
```

### **2. Через код:**
```python
# В handlers.py
docs_info = law_assistant.get_documents_info()
print(f"Загружено файлов: {docs_info['stats']['total_files']}")
```

### **3. Проверка базовой базы:**
```python
# Проверяем основную векторную базу
if os.path.exists("chroma_db_legal_bot_part1"):
    print("✅ Основная база законов найдена")
else:
    print("❌ Основная база отсутствует")
```

## 🎯 **Итог:**

**Документы берутся из ДВУХ источников:**

1. **`chroma_db_legal_bot_part1/`** - основные кодексы РФ (уже настроено)
2. **`documents/`** - дополнительные материалы (можно добавлять)

**Система автоматически:**
- Загружает документы при запуске
- Векторизует новые файлы
- Добавляет в поисковый индекс
- Использует для ответов пользователям

Вся система документов УЖЕ настроена и работает! 🚀⚖️