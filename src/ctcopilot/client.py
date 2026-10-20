"""Client for the ClinicalTrials.gov API v2 `/studies` endpoint.

Parameters used (checked against the official OpenAPI spec, v2.0.5):
- `query.cond`: Essie expression over the "Conditions or disease" search area.
- `filter.advanced`: Essie expression; used for phase and study type, because
  the endpoint has no dedicated filter parameters for those.
- `fields`: limits the response to `protocolSection` and `hasResults`.
- `pageSize`, `pageToken`: pagination; `nextPageToken` is absent on the last page.
- `countTotal`: asks for `totalCount` on the first page.

Every raw page is cached under `data/raw/<query-hash>/page_NNNN.json`, so a
re-run reads from disk instead of calling the API again.
"""

import hashlib
import json
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx

from ctcopilot import __version__
from ctcopilot.config import Settings

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_BACKOFF_S = 60.0


def build_query_params(settings: Settings) -> dict[str, str]:
    """Query parameters that stay the same on every page of one search."""
    cond = " OR ".join(f"({term})" for term in settings.conditions)
    phases = " OR ".join(settings.phases)
    return {
        "format": "json",
        "query.cond": cond,
        "filter.advanced": f"AREA[Phase]({phases}) AND AREA[StudyType]{settings.study_type}",
        "fields": "protocolSection|hasResults",
    }


def query_cache_dir(raw_dir: Path, params: dict[str, str], page_size: int) -> Path:
    """Directory for one search's pages, named by a hash of its parameters."""
    key = json.dumps({**params, "pageSize": page_size}, sort_keys=True)
    digest = hashlib.sha256(key.encode()).hexdigest()[:12]
    return raw_dir / digest


class StudiesClient:
    def __init__(
        self,
        settings: Settings,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.http = http or httpx.Client(
            base_url=settings.base_url,
            timeout=settings.timeout_s,
            headers={"User-Agent": f"ctcopilot/{__version__} (research project)"},
        )
        self._sleep = sleep
        self._last_request_at: float | None = None
        self.pages_from_cache = 0
        self.pages_from_api = 0

    def iter_pages(self, use_cache: bool = True) -> Iterator[dict[str, Any]]:
        """Yield every page of results, reading cached pages where they exist."""
        params = build_query_params(self.settings)
        cache_dir = query_cache_dir(self.settings.raw_dir, params, self.settings.page_size)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "params.json").write_text(json.dumps(params, indent=2), encoding="utf-8")

        page_token: str | None = None
        page_number = 1
        while True:
            path = cache_dir / f"page_{page_number:04d}.json"
            if use_cache and path.exists():
                page = json.loads(path.read_text(encoding="utf-8"))
                self.pages_from_cache += 1
            else:
                request_params: dict[str, str | int] = {
                    **params,
                    "pageSize": self.settings.page_size,
                }
                if page_token is None:
                    request_params["countTotal"] = "true"
                else:
                    request_params["pageToken"] = page_token
                page = self._get_json("/studies", request_params)
                path.write_text(json.dumps(page), encoding="utf-8")
                self.pages_from_api += 1

            yield page
            page_token = page.get("nextPageToken")
            if not page_token:
                return
            page_number += 1

    def _get_json(self, url: str, params: dict[str, str | int]) -> dict[str, Any]:
        """GET with rate limiting and retries on transient failures."""
        for attempt in range(self.settings.max_retries + 1):
            self._wait_for_rate_limit()
            retry_after: float | None = None
            try:
                response = self.http.get(url, params=params)
            except httpx.TransportError:
                if attempt == self.settings.max_retries:
                    raise
            else:
                if response.status_code not in RETRY_STATUS_CODES:
                    response.raise_for_status()
                    return response.json()
                if attempt == self.settings.max_retries:
                    response.raise_for_status()
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))

            backoff = min(self.settings.backoff_base_s * 2**attempt, MAX_BACKOFF_S)
            self._sleep(retry_after if retry_after is not None else backoff)
        raise RuntimeError("unreachable")

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            remaining = self.settings.min_request_interval_s - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = time.monotonic()


def _parse_retry_after(value: str | None) -> float | None:
    """Read a Retry-After header given in seconds; ignore other forms."""
    if value is None:
        return None
    try:
        return min(float(value), MAX_BACKOFF_S)
    except ValueError:
        return None
