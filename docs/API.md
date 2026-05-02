# Lesson Generator API

Base URL:

```text
http://localhost:28743
```

All endpoints except `/health/` require:

```text
X-API-Key: <your_api_key>
```

## Pipeline

```text
user_request
    ↓
/generate/brief/
    ↓
/generate/sections/
    ↓
/generate/style/
```

`/generate/brief/improve/` can be called whenever the user wants to adjust the brief.

For integrations that cannot keep long HTTP connections open, use the job endpoints instead:

```text
POST /jobs/generate/brief/       → GET /jobs/{job_id}/
POST /jobs/generate/sections/    → GET /jobs/{job_id}/
POST /jobs/generate/style/       → GET /jobs/{job_id}/
POST /jobs/generate/brief/improve/ → GET /jobs/{job_id}/
POST /jobs/generate/image/       → GET /jobs/{job_id}/
POST /jobs/generate/audio/       → GET /jobs/{job_id}/
```

## GET `/health/`

Response:

```json
{
  "status": "ok",
  "models_available": true
}
```

`models_available` is `true` when at least one Groq model in the unified pool is currently usable.

## Job endpoints

Job endpoints accept the same request bodies as their synchronous `/generate/.../` counterparts, but return immediately with a `job_id`.

Example:

```http
POST /jobs/generate/sections/
```

Request:

```json
{
  "topic": "Travel English",
  "brief": {
    "lesson_goal": "Help the student ask and answer practical train-station questions in English.",
    "vocabulary": ["ticket", "platform", "delay", "return ticket"],
    "grammar": [],
    "practical_skills": [
      {"type": "speaking", "title": "Station Role Play"}
    ]
  }
}
```

Immediate response:

```json
{
  "status": "queued",
  "job_id": "a0f5a2d1d7a04c58a8efc14f321d93a9",
  "job_type": "generate_sections"
}
```

Poll the job:

```http
GET /jobs/a0f5a2d1d7a04c58a8efc14f321d93a9/
```

Queued or running response:

```json
{
  "job_id": "a0f5a2d1d7a04c58a8efc14f321d93a9",
  "job_type": "generate_sections",
  "status": "running",
  "created_at": "2026-05-02T10:00:00+00:00",
  "updated_at": "2026-05-02T10:00:01+00:00",
  "result": null,
  "message": null
}
```

Successful response:

```json
{
  "job_id": "a0f5a2d1d7a04c58a8efc14f321d93a9",
  "job_type": "generate_sections",
  "status": "done",
  "created_at": "2026-05-02T10:00:00+00:00",
  "updated_at": "2026-05-02T10:01:12+00:00",
  "result": {
    "status": "ok",
    "sections": []
  },
  "message": null
}
```

Failed response:

```json
{
  "job_id": "a0f5a2d1d7a04c58a8efc14f321d93a9",
  "job_type": "generate_sections",
  "status": "error",
  "created_at": "2026-05-02T10:00:00+00:00",
  "updated_at": "2026-05-02T10:01:12+00:00",
  "result": {
    "status": "error",
    "message": "No Groq models are currently available"
  },
  "message": "No Groq models are currently available"
}
```

Polling recommendation for external services:

- create a job with `POST /jobs/generate/.../`
- store `job_id` on the client side
- poll `GET /jobs/{job_id}/` every 2-5 seconds
- stop polling when `status` is `done` or `error`
- read the generated payload from `result` when `status` is `done`
- treat HTTP `404` as an unknown or expired job

## POST `/generate/brief/`

Creates lesson topic and detailed brief.

Request:

```json
{
  "user_request": "A2 travel English lesson with vocabulary for train stations and speaking practice"
}
```

Response:

```json
{
  "status": "ok",
  "topic": "Travel English",
  "brief": {
    "lesson_goal": "Help the student ask and answer practical train-station questions in English during a one-on-one tutor lesson.",
    "vocabulary": ["ticket", "platform", "delay", "return ticket"],
    "grammar": [],
    "practical_skills": [
      {"type": "speaking", "title": "Station Role Play"}
    ]
  }
}
```

## POST `/generate/sections/`

Creates final lesson sections with tasks.

Request:

```json
{
  "topic": "Travel English",
  "brief": {
    "lesson_goal": "Help the student ask and answer practical train-station questions in English.",
    "vocabulary": ["ticket", "platform", "delay", "return ticket"],
    "grammar": [],
    "practical_skills": [
      {"type": "speaking", "title": "Station Role Play"},
      {"type": "writing", "title": "Travel Request"}
    ]
  }
}
```

Response shape:

```json
{
  "status": "ok",
  "sections": [
    {
      "title": "Vocabulary",
      "tasks": [
        {
          "type": "word_list",
          "pairs": [
            {"word": "ticket", "translation": "билет"},
            {"word": "platform", "translation": "платформа"},
            {"word": "delay", "translation": "задержка"},
            {"word": "return ticket", "translation": "билет туда и обратно"}
          ]
        },
        {
          "type": "fill_gaps",
          "mode": "open",
          "text": "Complete the sentences.\n1. I need a {{ticket}}.\n2. The train is on the {{platform}}.\n3. There is a {{delay}}.\n4. My {{boarding pass}} is missing.",
          "answers": ["ticket", "platform", "delay", "boarding pass"]
        },
        {
          "type": "match_cards",
          "pairs": [
            {"left": "ticket", "right": "a paper or digital pass for travel"},
            {"left": "platform", "right": "the place where you wait for a train"},
            {"left": "delay", "right": "when something is later than planned"}
          ]
        }
      ]
    }
  ]
}
```

## POST `/generate/style/`

Selects style values strictly from the provided lists.

Request:

```json
{
  "topic": "Travel English",
  "colors_available": ["blue", "green"],
  "icons_available": ["plane", "book"]
}
```

Response:

```json
{
  "status": "ok",
  "color": "blue",
  "icon": "plane"
}
```

## POST `/generate/brief/improve/`

Improves only the needed parts of an existing brief.

Request:

```json
{
  "topic": "Travel English",
  "brief": {
    "lesson_goal": "Help the student ask and answer practical train-station questions in English.",
    "vocabulary": ["ticket", "platform", "delay"],
    "grammar": [],
    "practical_skills": [
      {"type": "speaking", "title": "Station Role Play"}
    ]
  },
  "improvement_request": "add more vocabulary"
}
```

Response:

```json
{
  "status": "ok",
  "topic": "Travel English",
  "brief": {
    "lesson_goal": "Help the student ask and answer practical train-station questions in English.",
    "vocabulary": ["ticket", "platform", "delay", "return ticket", "single ticket", "timetable"],
    "grammar": [],
    "practical_skills": [
      {"type": "speaking", "title": "Station Role Play"}
    ]
  }
}
```

## POST `/generate/image/`

Generates an image from a detailed description.

## POST `/generate/audio/`

Generates audio from a monologue or dialogue script. The script text must be 3000 characters or fewer.
