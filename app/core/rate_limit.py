"""간단한 인메모리 rate limit (단일 프로세스·캡스톤 규모용)."""

from __future__ import annotations

from collections import defaultdict
from time import time

from fastapi import HTTPException, Request, status

_buckets: dict[str, list[float]] = defaultdict(list)


def enforce_rate_limit(
    request: Request,
    *,
    key_prefix: str,
    max_calls: int,
    window_sec: int,
) -> None:
    """IP 기준 슬iding window. 초과 시 429."""
    ip = request.client.host if request.client else "unknown"
    key = f"{key_prefix}:{ip}"
    now = time()
    window_start = now - window_sec
    hits = [t for t in _buckets[key] if t > window_start]
    if len(hits) >= max_calls:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
        )
    hits.append(now)
    _buckets[key] = hits
