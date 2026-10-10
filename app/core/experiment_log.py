import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

_lock = asyncio.Lock()


async def append_log(record: dict) -> None:
    """Append one request record as a JSON line when EXPERIMENT_LOG_PATH is set."""
    if not settings.EXPERIMENT_LOG_PATH:
        return
    path = Path(settings.EXPERIMENT_LOG_PATH)
    record = {"logged_at": datetime.now(timezone.utc).isoformat(), **record}
    line = json.dumps(record, ensure_ascii=False, default=str)
    async with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
