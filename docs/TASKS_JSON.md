# Tasks JSON

## Common rule

Every task must have a `type`.

Available task types:

```json
[
    "note",
    "reading_text",
    "word_list",
    "test",
    "true_or_false",
    "fill_gaps",
    "image",
    "match_cards",
    "audio",
    "speaking_cards",
    "words_to_pronounce"
]
```

---

# 1. note

Markdown + LaTeX content. `\n` is allowed for line breaks.  
By default, explanations should be in Russian unless explicitly requested otherwise.

```json
{
    "type": "note",
    "content": "Use **am/is/are** + verb-ing.\n\nExample: She is reading.\n\nFormula: $am/is/are + V_{ing}$"
}
```

---

# 2. reading_text

Markdown content. `\n` is allowed for line breaks.

```json
{
    "type": "reading_text",
    "content": "It is Saturday morning. **Tom is playing football** in the park. His sister is reading a book."
}
```

---

# 3. word_list

List of `word/phrase -> Russian translation` pairs.  
Must contain 5-15 pairs.

```json
{
    "type": "word_list",
    "pairs": [
        {
            "word": "run",
            "translation": "бегать"
        },
        {
            "word": "read",
            "translation": "читать"
        }
    ]
}
```

---

# 4. test

Quiz with 3–6 questions.  
Each question must have 2–4 options.  
`question` supports Markdown + LaTeX.  
Each question must have exactly one correct option.

```json
{
    "type": "test",
    "questions": [
        {
            "question": "Choose the correct form: **She ___ TV now.**",
            "options": [
                {
                    "option": "is watching",
                    "is_correct": true
                },
                {
                    "option": "watches",
                    "is_correct": false
                },
                {
                    "option": "watch",
                    "is_correct": false
                }
            ]
        }
    ]
}
```

---

# 5. true_or_false

Statements with boolean answers.  
`statement` supports Markdown + LaTeX.

```json
{
    "type": "true_or_false",
    "statements": [
        {
            "statement": "**Present Continuous** is used for actions happening now.",
            "is_true": true
        },
        {
            "statement": "We use Present Continuous for habits.",
            "is_true": false
        }
    ]
}
```

---

# 6. fill_gaps

Text with gaps and a separate list of answers.

Markdown + LaTeX is supported. `\n` is allowed for line breaks.

- `text` — text with gaps marked as `___`
- `answers` — list of correct answers in order

There are two modes:

- `open` — students see the answers and must match them to gaps
- `closed` — students must fill gaps without seeing answers

```json
{
    "type": "fill_gaps",
    "mode": "closed",
    "text": "Complete the sentences.\n\n1. She ___ TV now.\n2. They ___ football.\n\nFormula: $am/is/are + V_{ing}$",
    "answers": [
        "is watching",
        "are playing"
    ]
}
```

Open example:

```json
{
    "type": "fill_gaps",
    "mode": "open",
    "text": "Complete the sentences.\n\n1. I ___ a book.\n2. He ___ in the park.\n3. They ___ football.",
    "answers": [
        "am reading",
        "is running",
        "are playing"
    ]
}
```

---

# 7. image

Detailed image description only.

```json
{
    "type": "image",
    "detailed_description": "A bright classroom scene with five students. One student is writing on the board, two students are reading books, one student is looking out of the window, and one student is asking the teacher a question."
}
```

---

# 8. match_cards

Pairs for matching.

```json
{
    "type": "match_cards",
    "pairs": [
        {
            "left": "I",
            "right": "am reading"
        },
        {
            "left": "She",
            "right": "is playing"
        },
        {
            "left": "They",
            "right": "are running"
        }
    ]
}
```

---

# 9. audio

Audio script.

`audio_type` can be:

```json
"monologue"
```

---

# 10. speaking_cards

Array of short speaking prompts.

```json
{
    "type": "speaking_cards",
    "speaking_cards": [
        "Describe what you are doing right now.",
        "Ask your partner 3 questions about their weekend.",
        "Explain your morning routine in 4 sentences."
    ]
}
```

---

# 11. words_to_pronounce

Array of sound groups and words to pronounce.

```json
{
    "type": "words_to_pronounce",
    "words_to_pronounce": [
        {
            "sound": "/th/",
            "words": ["think", "three", "thank"]
        },
        {
            "sound": "/iː/",
            "words": ["see", "green", "teacher"]
        }
    ]
}
```

or:

```json
"dialogue"
```

The script is always an array of replicas.

## Monologue

```json
{
    "type": "audio",
    "audio_type": "monologue",
    "script": [
        {
            "speaker": "Narrator",
            "text": "It is Sunday morning. I am sitting in my room. My brother is playing computer games, and my mother is cooking breakfast."
        }
    ]
}
```

## Dialogue

```json
{
    "type": "audio",
    "audio_type": "dialogue",
    "script": [
        {
            "speaker": "Anna",
            "text": "Look! Tom is playing football."
        },
        {
            "speaker": "Ben",
            "text": "Yes, and Lisa is reading a book."
        },
        {
            "speaker": "Anna",
            "text": "What is Mike doing?"
        },
        {
            "speaker": "Ben",
            "text": "He is talking to the teacher."
        }
    ]
}
```
