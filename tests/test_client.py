import json
from collections.abc import Callable
from pathlib import Path

import httpx

from ctcopilot.client import StudiesClient
from ctcopilot.config import Settings

Handler = Callable[[httpx.Request], httpx.Response]


def make_client(tmp_path: Path, handler: Handler) -> tuple[StudiesClient, list[float]]:
    """A client backed by a fake transport; records sleeps instead of sleeping."""
    sleeps: list[float] = []
    settings = Settings(data_dir=tmp_path, min_request_interval_s=0)
    http = httpx.Client(base_url=settings.base_url, transport=httpx.MockTransport(handler))
    return StudiesClient(settings, http=http, sleep=sleeps.append), sleeps


def two_pages(request: httpx.Request) -> httpx.Response:
    if "pageToken" not in request.url.params:
        assert request.url.params["countTotal"] == "true"
        return httpx.Response(200, json={"studies": [{"id": 1}], "nextPageToken": "abc"})
    assert request.url.params["pageToken"] == "abc"
    return httpx.Response(200, json={"studies": [{"id": 2}]})


def test_follows_next_page_token(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path, two_pages)
    pages = list(client.iter_pages())
    assert [p["studies"][0]["id"] for p in pages] == [1, 2]
    assert client.pages_from_api == 2


def test_second_run_reads_from_cache(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path, two_pages)
    list(client.iter_pages())

    def fail(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not call the API")

    cached_client, _ = make_client(tmp_path, fail)
    pages = list(cached_client.iter_pages())
    assert len(pages) == 2
    assert cached_client.pages_from_cache == 2
    cached_files = sorted(p.name for p in (tmp_path / "raw").rglob("page_*.json"))
    assert cached_files == ["page_0001.json", "page_0002.json"]
    first = json.loads(next((tmp_path / "raw").rglob("page_0001.json")).read_text())
    assert first["nextPageToken"] == "abc"


def test_retries_transient_errors_with_backoff(tmp_path: Path) -> None:
    responses = iter(
        [
            httpx.Response(503),
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json={"studies": []}),
        ]
    )
    client, sleeps = make_client(tmp_path, lambda request: next(responses))
    pages = list(client.iter_pages())
    assert pages == [{"studies": []}]
    assert sleeps == [2.0, 7.0]  # exponential backoff, then the server's Retry-After
