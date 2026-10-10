import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings

_hits: dict[str, deque[float]] = defaultdict(deque)


async def rate_limit(request: Request) -> None:
    """Sliding one-minute window per API key or client IP; each request costs LLM quota."""
    limit = settings.RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        return
    client = request.headers.get("X-API-Key") or (request.client.host if request.client else "-")
    now = time.monotonic()
    hits = _hits[client]
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= limit:
        retry = int(60 - (now - hits[0])) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
            headers={"Retry-After": str(retry)},
        )
    hits.append(now)
