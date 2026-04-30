# Lesson Generator API

Base URL:

```
http://localhost:28743
```

---

## Authentication

All endpoints (except `/health/`) require header:

```
X-API-Key: <your_api_key>
```

---

## Common Response Format

### Success

```json
{
    "status": "ok",
    ...
}
```

### Error

```json
{
    "status": "error",
    "message": "Error description"
}
```

---

## Contract Update (2026-04-30)

1. `/generate/references/`:
- `reference` no longer contains `lesson_topic`.
- Current `reference` schema:
```json
{
    "section_goal": "string",
    "key_points": ["string"],
    "practice_focus": "string"
}
```

2. `/generate/tasks-plan/`:
- Request now requires top-level `lesson_topic`.
- `sections[].reference` must use the same schema as `/generate/references/` (without `lesson_topic`).
- Response format remains the same as current implementation (includes `title`, `reference`, `tasks` for each section).

3. Language default:
- Explanatory content is generated in Russian by default, unless another language is explicitly requested.

---

# 1. Health Check

### GET `/health/`

#### Response

```json
{
    "status": "ok"
}
```

---

# 2. Generate Meta

### POST `/generate/meta/`

Generates lesson meta.

`subject` input modes:
- provide `subject` when it is already known (no subject selection);
- or provide `subjects_available` to let the model choose one value from the list.
- do not send both fields in one request.

#### Request

```json
{
    "user_request": "Present Continuous lesson for 5th grade",
    "subjects_available": ["English", "Math"],
    "colors_available": ["blue", "green"],
    "icons_available": ["book", "pencil"]
}
```

#### Alternative Request (fixed subject)

```json
{
    "user_request": "Present Continuous lesson for 5th grade",
    "subject": "English",
    "colors_available": ["blue", "green"],
    "icons_available": ["book", "pencil"]
}
```

#### Response

```json
{
    "status": "ok",
    "topic": "Present Continuous",
    "subject": "English",
    "color": "blue",
    "icon": "book"
}
```

---

# 3. Generate Sections

### POST `/generate/sections/new/`

Generates lesson sections.

#### Request

```json
{
    "user_request": "Present Continuous lesson"
}
```

#### Response

```json
{
    "status": "ok",
    "sections": [
        { "title": "Warm-up" },
        { "title": "Form Basics" },
        { "title": "Usage Rules" }
    ]
}
```

---

# 4. Improve Sections

### POST `/generate/sections/improve/`

Improves section titles.

#### Request

```json
{
    "user_request": "Present Continuous lesson",
    "sections": [
        { "title": "Warm-up" },
        { "title": "Form Basics" },
        { "title": "Usage Rules" }
    ],
    "improvement_request": "Make it more practical"
}
```

#### Response

```json
{
    "status": "ok",
    "sections": [
        { "title": "Quick Start" },
        { "title": "Practical Forms" },
        { "title": "Real Usage" }
    ]
}
```

---

# 5. Generate References

### POST `/generate/references/`

Generates structured reference for each section.
Processing mode: section-by-section (sequentially), then aggregated into `sections`.

#### Request

```json
{
    "user_request": "Present Continuous lesson",
    "topic": "Present Continuous",
    "sections": [
        { "title": "Form Basics" }
    ]
}
```

#### Response

```json
{
    "status": "ok",
    "sections": [
        {
            "title": "Form Basics",
            "reference": {
                "section_goal": "Teach how to form sentences",
                "key_points": [
                    "am/is/are + verb-ing"
                ],
                "practice_focus": "Build sentences"
            }
        }
    ]
}
```

---

# 6. Generate Tasks Plan

### POST `/generate/tasks-plan/`

Generates task plan (types + purpose).
Processing mode: section-by-section (sequentially), then aggregated into `sections`.

#### Request

```json
{
    "lesson_topic": "Present Continuous",
    "sections": [
        {
            "title": "Form Basics",
            "reference": {
                "section_goal": "Teach how to form sentences",
                "key_points": ["am/is/are + verb-ing"],
                "practice_focus": "Build sentences"
            }
        }
    ]
}
```

#### Response

```json
{
    "status": "ok",
    "sections": [
        {
            "title": "Form Basics",
            "reference": {
                "section_goal": "Teach how to form sentences",
                "key_points": ["am/is/are + verb-ing"],
                "practice_focus": "Build sentences"
            },
            "tasks": [
                {
                    "type": "note",
                    "purpose": "Explain grammar"
                },
                {
                    "type": "fill_gaps",
                    "purpose": "Practice sentence building"
                }
            ]
        }
    ]
}
```

---

# 7. Generate Tasks

### POST `/generate/tasks/`

Generates full tasks for one section.

#### Request

```json
{
    "lesson_topic": "Present Continuous",
    "section_title": "Form Basics",
    "tasks": [
        { "type": "note", "purpose": "Explain grammar" },
        { "type": "fill_gaps", "purpose": "Practice" }
    ]
}
```

#### Response

```json
{
    "status": "ok",
    "section": {
        "title": "Form Basics",
        "tasks": [
            {
                "type": "note",
                "content": "Use am/is/are..."
            },
            {
                "type": "fill_gaps",
                "mode": "closed",
                "text": "She ___ TV now.",
                "answers": ["is watching"]
            }
        ]
    }
}
```

---

# 8. Generate Image

### POST `/generate/image/`

Generates image from description.

#### Request

```json
{
    "detailed_description": "A bright classroom scene",
    "size": "1024x1024",
    "quality": "medium",
    "response_format": "b64_json"
}
```

#### Response

```json
{
    "status": "ok",
    "response_format": "b64_json",
    "image": "<base64_string>"
}
```

#### Notes

- Max size: **15MB**
- If exceeded → error

---

# 9. Generate Audio

### POST `/generate/audio/`

Generates audio from script.

#### Request

```json
{
    "audio_type": "dialogue",
    "voice": "nova",
    "response_format": "mp3",
    "speed": 1.0,
    "script": [
        { "speaker": "Anna", "text": "Hello!" },
        { "speaker": "Ben", "text": "Hi!" }
    ]
}
```

#### Response

```json
{
    "status": "ok",
    "response_format": "mp3",
    "audio_base64": "<base64_string>"
}
```

#### Notes

- Max size: **15MB**
- Script length should not exceed ~3000–4000 characters
- Monologue → 1 speaker
- Dialogue → ≥2 speakers, ≥4 replicas

---

# Pipeline Overview

```
user_request
    ↓
/generate/meta/
    ↓
/generate/sections/new/
    ↓
/generate/references/
    ↓
/generate/tasks-plan/
    ↓
/generate/tasks/
    ↓
(optional)
/generate/image/
/generate/audio/
```

---

# Errors

Common reasons:

- Invalid API key → 401
- Invalid input → 422
- LLM failed validation → retry → error
- Media > 15MB → error
