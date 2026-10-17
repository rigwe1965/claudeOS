import uuid
from datetime import datetime, timezone


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_str() -> str:
    return utcnow().isoformat()


def first_text(response) -> str:
    """Text of the first `text` block in a Messages API response.

    Models with thinking on by default put a `thinking` block first, so `content[0].text`
    raises AttributeError on them. Returns "" when the response has no text block.
    """
    for block in (getattr(response, "content", None) or []):
        if getattr(block, "type", None) == "text":
            return getattr(block, "text", "") or ""
    return ""
