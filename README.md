# Telegram Bot for 1С MCP Integration

Telegram бот для работы с 1С через MCP (Model Context Protocol) с поддержкой различных AI-моделей.

## Возможности

- **Интеграция с 1С** через MCP-сервер
- **Поддержка различных AI-моделей**: DeepSeek, OpenAI, Anthropic, Google Gemini
- **Автоматический анализ ошибок** и уточнение запросов
- **Кэширование структур метаданных** для повышения производительности
- **Контекст диалога** (до 20 сообщений)
- **Basic-аутентификация** для MCP-сервера

## Установка

### 1. Предварительные требования

- Python 3.8 или выше
- Telegram Bot Token (получить у [@BotFather](https://t.me/botfather))
- API-ключ для выбранной AI-модели
- Доступ к MCP-серверу 1С

### 2. Клонирование репозитория

```bash
git clone <repository-url>
cd telegram-1c-mcp-bot
```

### 3. Создание виртуального окружения

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate     # Windows
```

### 4. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 5. Настройка конфигурации

Скопируйте файл `.env.example` в `.env` и отредактируйте:

```bash
cp .env.example .env
```

Отредактируйте файл `.env`:

```env
# Токен Telegram бота (обязательно)
BOT_TOKEN=ваш_токен_бота

# Разрешенные chat ID (опционально, через запятую)
# Если не указано — бот отвечает всем
# Если указано — только указанным chat ID
ALLOWED_CHAT_IDS=123456789,987654321

# Настройки AI-модели
AI_MODEL_PROVIDER=deepseek  # deepseek, openai, anthropic, google
AI_MODEL_API_KEY=ваш_api_ключ
AI_MODEL_BASE_URL=https://api.deepseek.com/v1/chat/completions
AI_MODEL_NAME=deepseek-chat

# Настройки MCP-сервера 1С
MCP_SERVER_URL=http://127.0.0.1:8080/mcp
MCP_AUTH_USERNAME=          # опционально
MCP_AUTH_PASSWORD=          # опционально

# Лимит итераций для уточнения запросов
MAX_ITERATIONS=5

# Настройки логирования
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log       # опционально
LOG_MAX_BYTES=10485760      # 10 MB
LOG_BACKUP_COUNT=5
```

### 6. Настройка ограничения доступа (опционально)

Если вы хотите ограничить доступ к боту только определённым пользователям:

1. Получите chat ID пользователя (можно использовать бота @userinfobot)
2. Укажите chat ID через запятую в `ALLOWED_CHAT_IDS`:

```env
ALLOWED_CHAT_IDS=123456789,987654321
```

Если переменная пустая или не указана — бот отвечает всем.

### 7. Настройка MCP-сервера 1С

Убедитесь, что у вас настроен MCP-сервер для 1С. Пример конфигурации для 1С:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": {}
}
```

Сервер должен поддерживать следующие инструменты:
- `list_metadata_objects` — список объектов метаданных
- `get_metadata_structure` — структура конкретного объекта
- Другие инструменты для работы с данными

## Использование

### Запуск бота

```bash
python bot.py
```

### Команды бота

- `/start` — приветственное сообщение
- `/help` — справка по командам и настройкам
- `/clear` — очистить историю диалога

### Примеры запросов

Отправьте боту запрос на естественном языке:

```
Какие документы продаж были вчера?
```

```
Сколько товаров осталось на складе?
```

```
Покажи структуру документа РеализацияТоваровУслуг
```

### Как это работает

1. Пользователь отправляет запрос боту
2. AI-модель анализирует запрос и определяет необходимые MCP-инструменты
3. Бот выполняет MCP-запросы к серверу 1С
4. При ошибках AI-модель анализирует ответ и уточняет запрос (до MAX_ITERATIONS раз)
5. Результат форматируется и отправляется пользователю

## Конфигурация AI-моделей

### DeepSeek (по умолчанию)

```env
AI_MODEL_PROVIDER=deepseek
AI_MODEL_API_KEY=ваш_ключ_deepseek
AI_MODEL_BASE_URL=https://api.deepseek.com/v1/chat/completions
AI_MODEL_NAME=deepseek-chat
```

### OpenAI

```env
AI_MODEL_PROVIDER=openai
AI_MODEL_API_KEY=sk-ваш_ключ_openai
AI_MODEL_BASE_URL=https://api.openai.com/v1/chat/completions
AI_MODEL_NAME=gpt-4o
```

### Anthropic

```env
AI_MODEL_PROVIDER=anthropic
AI_MODEL_API_KEY=sk-ant-ваш_ключ_anthropic
AI_MODEL_BASE_URL=https://api.anthropic.com/v1/messages
AI_MODEL_NAME=claude-3-5-sonnet-20241022
```

### Google Gemini

```env
AI_MODEL_PROVIDER=google
AI_MODEL_API_KEY=ваш_ключ_google
AI_MODEL_BASE_URL=https://generativelanguage.googleapis.com/v1beta/models
AI_MODEL_NAME=gemini-1.5-pro
```

## Кэширование

Бот автоматически кэширует результаты `get_metadata_structure` в папку `contexts/structure/`. Это позволяет:

- Уменьшить количество запросов к серверу 1С
- Ускорить повторные запросы к тем же объектам
- Не увеличивать счётчик итераций при использовании кэша

Кэш очищается только вручную (удалением файлов).

## Логирование

Логи сохраняются в файл `logs/bot.log` (если настроено) и выводятся в консоль. Уровень логирования настраивается через `LOG_LEVEL`:

- `DEBUG` — подробные логи, включая запросы/ответы
- `INFO` — основная информация о работе
- `WARNING` — только предупреждения и ошибки
- `ERROR` — только ошибки

## Структура проекта

```
telegram-1c-mcp-bot/
├── bot.py                 # Основной файл бота
├── ai_client.py           # Клиент для работы с AI-моделями
├── mcp_client_1c.py       # Клиент для MCP-сервера 1С
├── context_manager.py     # Управление контекстом диалога
├── requirements.txt       # Зависимости Python
├── .env.example          # Пример конфигурации
├── README.md             # Эта документация
├── contexts/             # Контекстные файлы и кэш
│   ├── 01_system.md
│   ├── 02_instruments.md
│   ├── 03_syntax_1c.md
│   └── structure/        # Кэш структур метаданных
└── logs/                 # Логи (создаётся автоматически)
```

## Разработка

### Добавление новой AI-модели

1. Добавьте конфигурацию провайдера в `ai_client.py` в словарь `_provider_configs`
2. Реализуйте методы `_build_headers`, `_build_payload`, `_extract_response` для нового провайдера
3. Обновите документацию

### Тестирование

```bash
# Проверка синтаксиса
python -m py_compile *.py

# Запуск в режиме разработки
LOG_LEVEL=DEBUG python bot.py
```

## Устранение неполадок

### Бот не запускается

1. Проверьте токен бота в `.env`
2. Убедитесь, что установлены все зависимости
3. Проверьте логи на наличие ошибок

### Ошибки подключения к MCP-серверу

1. Проверьте `MCP_SERVER_URL`
2. Убедитесь, что сервер доступен
3. Проверьте настройки аутентификации (если требуется)

### Ошибки AI-API

1. Проверьте API-ключ
2. Убедитесь, что провайдер поддерживает выбранную модель
3. Проверьте баланс API-аккаунта

## Лицензия

[Указать лицензию]

## Контрибьютинг

1. Форкните репозиторий
2. Создайте ветку для вашей функции
3. Внесите изменения
4. Создайте Pull Request

## Благодарности

- [aiogram](https://docs.aiogram.dev/) — асинхронный фреймворк для Telegram Bot API
- [httpx](https://www.python-httpx.org/) — асинхронный HTTP-клиент
- Разработчикам MCP-протокола и интеграции с 1С