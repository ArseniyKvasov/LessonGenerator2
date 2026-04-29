def trim_to_words_limit(text: str, max_words: int) -> str:
    words = text.split()

    if len(words) <= max_words:
        return text.strip()

    return " ".join(words[:max_words]).strip()


def trim_topic_to_chars(topic: str, max_chars: int = 40) -> str:
    """
    Trims topic by removing words from the end until it fits max_chars.
    If one remaining word is still too long, trims it by characters.
    """
    topic = " ".join(topic.split()).strip()

    if len(topic) <= max_chars:
        return topic

    words = topic.split()

    while len(" ".join(words)) > max_chars and len(words) > 1:
        words.pop()

    trimmed_topic = " ".join(words).strip()

    if len(trimmed_topic) > max_chars:
        trimmed_topic = trimmed_topic[:max_chars].rstrip()

    return trimmed_topic