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

Сервис выбирает случайную модель на каждый запрос из списков в [app/config.py](/Users/arseniy/PycharmProjects/LessonGenerator2/app/config.py).

Light-модели:
- `llama-3.1-8b-instant`
- `gemma2-9b-it`
- `allam-2-7b`
- `openai/gpt-oss-20b`
- `meta-llama/llama-4-scout-17b-16e-instruct`

Pro-модели:
- `llama-3.3-70b-versatile`
- `qwen/qwen3-32b`
- `openai/gpt-oss-120b`

### Важное по `/generate/meta/`

- Передавайте `subjects_available`.
- Сервис выбирает `subject` строго из `subjects_available`.

### Важное по pipeline генерации

- `/generate/references/` и `/generate/tasks-plan/` обрабатывают все разделы одним batch-запросом и возвращают агрегированный результат.
- `/generate/tasks/` принимает один раздел (`lesson_topic`, `section_title`, `reference_points`, `tasks`) и генерирует задания только для него.

### Язык по умолчанию

- Объяснения и учебные формулировки генерируются на русском языке, если в запросе явно не указан другой язык.

## Production заметки

- Базовый образ: `python:3.9-slim`
- Контейнер запускается под non-root пользователем
- Включен `HEALTHCHECK` на `/health/`
- Перезапуск сервиса: `unless-stopped`

## Логи API

- Файл логов: `logs/api.log`
- Для каждого HTTP-запроса логируется:
  - метод и путь
  - статус ответа
  - длительность обработки в миллисекундах
  - тело запроса
  - тело ответа

## Остановка

```bash
docker compose down
```
