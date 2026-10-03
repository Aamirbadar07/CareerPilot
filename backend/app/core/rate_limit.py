import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


def rate_limit(max_calls: int, per_seconds: int):
    """FastAPI dependency: at most max_calls per client IP in a sliding window."""
    # ponytail: in-process memory, so the limit is per worker and resets on restart.
    # Move to Redis when the backend runs more than one worker.
    hits: dict[str, deque[float]] = defaultdict(deque)

    def check(request: Request) -> None:
        now = time.monotonic()
        window = hits[request.client.host if request.client else "unknown"]
        while window and window[0] <= now - per_seconds:
            window.popleft()
        if len(window) >= max_calls:
            raise HTTPException(
                429, "Too many requests. Try again later.", {"Retry-After": str(per_seconds)}
            )
        window.append(now)

    return check
