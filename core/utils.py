import uuid
from datetime import datetime, timezone


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_str() -> str:
    return utcnow().isoformat()
