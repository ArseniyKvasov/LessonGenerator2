# Lesson Generator API

API для генерации структурированных one-on-one ESL уроков: brief, секции с готовыми заданиями, стиль, улучшение brief и медиа.

## Технологии

- Python 3.9
- FastAPI
- Uvicorn
- Docker / Docker Compose

## Быстрый старт

1. Создайте env-файл:

```bash
cp .env.example .env
```

2. Заполните значения:

- `API_KEY`
- `GROQ_API_KEY`
- `POLLINATIONS_API_KEY`

3. Соберите и запустите контейнер:

```bash
docker compose up --build -d
```

4. Проверьте состояние сервиса:

```bash
curl http://localhost:28743/health/
```

Ожидаемый ответ:

```json
{"status":"ok","models_available":true}
```

## Локальный запуск

```bash
python3.9 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 28743 --workers 2
```

## Аутентификация

Все endpoint'ы, кроме `/health/`, требуют заголовок:

```text
X-API-Key: <your_api_key>
```

## Основной pipeline

1. `POST /generate/brief/` — создает topic и lesson brief из `user_request`.
2. `POST /generate/sections/` — создает финальные секции с заданиями из `topic` и `brief`.
3. `POST /generate/style/` — выбирает `color` и `icon` строго из переданных списков.
4. `POST /generate/brief/improve/` — точечно улучшает brief по пользовательскому запросу.

Дополнительно доступны:

- `POST /generate/image/`
- `POST /generate/audio/`

Подробные примеры: [docs/API.md](docs/API.md)

## Модели Groq

Используется единый пул моделей:

```env
MODEL_POOL=llama-3.3-70b-versatile,qwen/qwen3-32b,openai/gpt-oss-120b
DEFAULT_MODEL_COOLDOWN_SECONDS=60
MAX_GENERATION_ATTEMPTS=3
```

Если Groq возвращает rate limit, сервис извлекает retry time из сообщения и временно исключает модель из пула.

## Тесты

```bash
.venv/bin/python -m pytest
```

## Логи API

Файл логов: `logs/api.log`.

Для каждого HTTP-запроса логируются метод, путь, статус, длительность, тело запроса и тело ответа.
