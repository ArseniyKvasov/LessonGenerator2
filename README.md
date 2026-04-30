# Lesson Generator API

API для генерации структуры урока, секций, reference-материалов, заданий и медиа (изображение/аудио).

## Технологии

- Python 3.9
- FastAPI
- Uvicorn
- Docker / Docker Compose

## Быстрый старт (Docker Compose, production)

1. Создайте env-файл:

```bash
cp .env.example .env
```

2. Заполните значения в `.env`:

- `API_KEY`
- `GROQ_API_KEY`
- `POLLINATIONS_API_KEY`

3. Соберите и запустите контейнер:

```bash
docker compose up --build -d
```

4. Проверьте health endpoint:

```bash
curl http://localhost:28743/health/
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

## Локальный запуск (без Docker)

1. Python 3.9 и venv:

```bash
python3.9 -m venv .venv
source .venv/bin/activate
```

2. Установка зависимостей:

```bash
pip install -r requirements.txt
```

3. Подготовка окружения:

```bash
cp .env.example .env
```

4. Старт приложения:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 28743 --workers 2
```

## Аутентификация

Все endpoint'ы (кроме `/health/`) требуют заголовок:

```text
X-API-Key: <your_api_key>
```

## Основные endpoint'ы

- `GET /health/`
- `POST /generate/meta/`
- `POST /generate/sections/new/`
- `POST /generate/sections/improve/`
- `POST /generate/references/`
- `POST /generate/tasks-plan/`
- `POST /generate/tasks/`
- `POST /generate/image/`
- `POST /generate/audio/`

Подробные примеры запросов/ответов: [docs/API.md](docs/API.md)

## Модели Groq

Поддерживаемые значения `LIGHT_MODEL`:
- `llama-3.1-8b-instant`
- `gemma2-9b-it`
- `llama-3.1-70b-versatile`
- `openai/gpt-oss-20b`

Поддерживаемые значения `PRO_MODEL`:
- `llama-3.3-70b-versatile`
- `llama-3.1-405b-reasoning`
- `deepseek-r1-distill-llama-70b`
- `openai/gpt-oss-120b`

### Важное по `/generate/meta/`

- Передавайте либо `subject`, либо `subjects_available`.
- Если передан `subject`, сервис использует его как фиксированное значение и не выбирает предмет из списка.
- Если передан `subjects_available`, сервис выбирает `subject` из этого списка.

### Важное по pipeline генерации

- `/generate/references/` и `/generate/tasks-plan/` обрабатывают урок пораздельно (section-by-section) и возвращают агрегированный результат.
- `/generate/tasks/` принимает один раздел (`lesson_topic`, `section_title`, `tasks`) и генерирует задания только для него.

### Язык по умолчанию

- Объяснения и учебные формулировки генерируются на русском языке, если в запросе явно не указан другой язык.

## Production заметки

- Базовый образ: `python:3.9-slim`
- Контейнер запускается под non-root пользователем
- Включен `HEALTHCHECK` на `/health/`
- Перезапуск сервиса: `unless-stopped`

## Остановка

```bash
docker compose down
```
