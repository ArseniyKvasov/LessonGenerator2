# Task JSON

All generated lesson sections use this shape:

```json
{
  "title": "Section title",
  "tasks": []
}
```

## `note`

Markdown support material or student instruction.

```json
{
  "type": "note",
  "content": "**Rule**\n\nExample sentence."
}
```

## `word_list`

English word or phrase with Russian translation.

```json
{
  "type": "word_list",
  "pairs": [
    {"word": "ticket", "translation": "билет"},
    {"word": "platform", "translation": "платформа"},
    {"word": "delay", "translation": "задержка"}
  ]
}
```

## `fill_gaps`

Open mode is used for vocabulary. Closed mode is used for grammar.
Rules:
- 4-10 gaps per task
- one gap per sentence is recommended
- answers order must match gap order
- base words (if needed) stay in text, for example `(cook)`
- app parses `___` into `{{answer}}` programmatically

```json
{
  "type": "fill_gaps",
  "mode": "closed",
  "text": "1. He {{is cooking}} (cook) dinner now.\n2. They {{are studying}} (study) at home.\n3. I {{am drinking}} (drink) tea.\n4. We {{are waiting}} (wait) outside.",
  "answers": ["is cooking", "are studying", "am drinking", "are waiting"]
}
```

## `match_cards`

Phrase matching or word-definition matching.

```json
{
  "type": "match_cards",
  "pairs": [
    {"left": "platform", "right": "the place where you wait for a train"},
    {"left": "delay", "right": "when something is later than planned"},
    {"left": "ticket", "right": "a paper or digital pass for travel"}
  ]
}
```

## `test`

Multiple choice. The application shuffles options programmatically.

```json
{
  "type": "test",
  "questions": [
    {
      "question": "Choose the correct sentence.",
      "options": [
        {"option": "She is reading.", "is_correct": true},
        {"option": "She reading.", "is_correct": false}
      ]
    },
    {
      "question": "Choose the correct form: They ___.",
      "options": [
        {"option": "are working", "is_correct": true},
        {"option": "is working", "is_correct": false}
      ]
    },
    {
      "question": "Choose the correct question.",
      "options": [
        {"option": "What are you doing?", "is_correct": true},
        {"option": "What you are doing?", "is_correct": false}
      ]
    }
  ]
}
```

## `true_false`

Text or script comprehension statements.

```json
{
  "type": "true_false",
  "statements": [
    {"statement": "The speaker needs a ticket.", "is_true": true},
    {"statement": "The train is early.", "is_true": false},
    {"statement": "The speaker asks for help.", "is_true": true}
  ]
}
```

## `text_input`

Writing answer box.

```json
{
  "type": "text_input",
  "title": "Short reply",
  "default_text": ""
}
```

## `image`

Generated image stored directly in the task.

```json
{
  "type": "image",
  "detailed_description": "A train station scene for ESL speaking practice.",
  "response_format": "b64_json",
  "image": "..."
}
```

## `audio`

Generated audio stored directly in the task.

```json
{
  "type": "audio",
  "audio_type": "dialogue",
  "script": [
    {"speaker": "A", "text": "Where is platform two?"},
    {"speaker": "B", "text": "It is over there."}
  ],
  "response_format": "mp3",
  "audio_base64": "..."
}
```

## `speaking_cards`

Markdown speaking prompt with numbered questions.

```json
{
  "type": "speaking_cards",
  "content": "*Read and answer the questions*\n\n1. What do you need at a train station?\n2. How can you ask for help?\n3. What would you say if your train is late?"
}
```
