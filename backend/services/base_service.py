"""Shared client for optional upstream data services.

The old client blocked async request handlers, kept an unbounded process-local
cache, and silently substituted generated fixtures whenever a live call failed.
This implementation keeps the existing synchronous service interface for
compatibility but makes provenance and failure explicit. Callers should move
network work to an async adapter or thread pool in a later API refactor.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from typing import Any, Dict, Optional

import requests

from backend.config import APIConfig


class ExternalServiceError(RuntimeError):
    """An optional upstream service could not return a validated response."""


class BaseAPIService:
    """Bounded, thread-safe synchronous HTTP adapter with explicit failures."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        if not base_url or not base_url.strip():
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._request_times: deque[float] = deque()
        self._lock = threading.RLock()

    def _check_rate_limit(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._request_times and now - self._request_times[0] >= 60:
                    self._request_times.popleft()
                if len(self._request_times) < APIConfig.MAX_REQUESTS_PER_MINUTE:
                    self._request_times.append(now)
                    return
                sleep_for = max(0.01, 60 - (now - self._request_times[0]))
            time.sleep(sleep_for)

    def _get_from_cache(self, key: str) -> Optional[Any]:
        if not APIConfig.CACHE_ENABLED:
            return None
        with self._lock:
            cached = self._cache.get(key)
            if cached is None:
                return None
            value, timestamp = cached
            if time.monotonic() - timestamp >= APIConfig.CACHE_TTL:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return value

    def _set_cache(self, key: str, value: Any) -> None:
        if not APIConfig.CACHE_ENABLED:
            return
        with self._lock:
            self._cache[key] = (value, time.monotonic())
            self._cache.move_to_end(key)
            while len(self._cache) > APIConfig.CACHE_MAX_ENTRIES:
                self._cache.popitem(last=False)

    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Return a live JSON response or raise ``ExternalServiceError``."""

        if APIConfig.MOCK_MODE:
            raise ExternalServiceError(
                "Legacy mock service data is disabled; inject an explicit test fixture instead"
            )

        normalized_method = method.upper()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        cache_key = f"{normalized_method}:{url}:{sorted((params or {}).items())}"
        if normalized_method == "GET":
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return cached

        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error: Optional[Exception] = None
        for attempt in range(APIConfig.MAX_RETRIES):
            self._check_rate_limit()
            try:
                response = self.session.request(
                    method=normalized_method,
                    url=url,
                    params=params,
                    json=data,
                    headers=headers,
                    timeout=APIConfig.REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                result = response.json()
                if normalized_method == "GET":
                    self._set_cache(cache_key, result)
                return result
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt + 1 < APIConfig.MAX_RETRIES:
                    time.sleep(APIConfig.RETRY_BACKOFF_FACTOR * (2**attempt))

        raise ExternalServiceError(f"External service request failed for {endpoint}") from last_error
