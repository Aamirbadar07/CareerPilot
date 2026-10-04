import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.core.config import settings


def client_key(request: Request) -> str:
    """The caller's address, read from the right of X-Forwarded-For.

    Each proxy in front of the app appends the address it was called from, so the last
    TRUSTED_PROXY_HOPS entries were written by infrastructure and the one before them is the
    caller. Everything further left came from the caller: Cloud Run and Render append to the
    header rather than replacing it, so counting from the left lets anyone reset their own
    limit with a made-up header. A header too short to hold the expected hops is ignored
    entirely in favour of the socket address, which no caller can choose.
    """
    forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",")]
    forwarded = [part for part in forwarded if part]
    hops = settings.trusted_proxy_hops
    if hops and len(forwarded) >= hops:
        return forwarded[-hops]
    return request.client.host if request.client else "unknown"


def rate_limit(max_calls: int, per_seconds: int):
    """FastAPI dependency: at most max_calls per client IP in a sliding window."""
    # ponytail: in-process memory, so the limit is per worker and resets on restart.
    # Move to Redis when the backend runs more than one worker.
    hits: dict[str, deque[float]] = defaultdict(deque)

    def check(request: Request) -> None:
        now = time.monotonic()
        window = hits[client_key(request)]
        while window and window[0] <= now - per_seconds:
            window.popleft()
        if len(window) >= max_calls:
            raise HTTPException(
                429, "Too many requests. Try again later.", {"Retry-After": str(per_seconds)}
            )
        window.append(now)

    return check
