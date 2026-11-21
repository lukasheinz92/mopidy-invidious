"""Thin, thread-safe wrapper around the Invidious REST API (/api/v1)."""

from __future__ import annotations

import logging
import threading
import time
import urllib.parse
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Invidious returns up to ~200 videos per playlist page; stop eventually.
MAX_PLAYLIST_PAGES = 10


class InvidiousError(Exception):
    pass


class _TTLCache:
    def __init__(self, ttl: int, max_size: int = 2048) -> None:
        self._ttl = ttl
        self._max_size = max_size
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            expires, value = entry
            if expires < time.monotonic():
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        if self._ttl <= 0:
            return
        with self._lock:
            if len(self._data) >= self._max_size:
                # Drop the oldest-inserted entry; good enough for this workload.
                self._data.pop(next(iter(self._data)))
            self._data[key] = (time.monotonic() + self._ttl, value)


class InvidiousClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 15,
        user_agent: str | None = None,
        proxy: str | None = None,
        cache_ttl: int = 3600,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=f"{self.base_url}/api/v1",
            timeout=timeout,
            headers={"User-Agent": user_agent} if user_agent else None,
            proxy=proxy,
            follow_redirects=True,
        )
        self._cache = _TTLCache(cache_ttl)

    def close(self) -> None:
        self._http.close()

    def _get(self, path: str, **params: Any) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        try:
            response = self._http.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            detail = _error_detail(exc.response)
            msg = f"Invidious {path} returned {exc.response.status_code}: {detail}"
            raise InvidiousError(msg) from exc
        except (httpx.HTTPError, ValueError) as exc:
            msg = f"Invidious {path} failed: {exc}"
            raise InvidiousError(msg) from exc

    def _cached(self, key: str, path: str, **params: Any) -> Any:
        value = self._cache.get(key)
        if value is None:
            value = self._get(path, **params)
            self._cache.set(key, value)
        return value

    def stats(self) -> dict[str, Any]:
        return self._get("/stats")

    def search(
        self, query: str, *, type: str = "video", page: int = 1
    ) -> list[dict[str, Any]]:
        return self._get("/search", q=query, type=type, page=page)

    def video(self, video_id: str) -> dict[str, Any]:
        return self._cached(f"video:{video_id}", f"/videos/{video_id}", local="true")

    def playlist(self, playlist_id: str) -> dict[str, Any]:
        key = f"playlist:{playlist_id}"
        if (cached := self._cache.get(key)) is not None:
            return cached

        result = self._get(f"/playlists/{playlist_id}")
        videos = list(result.get("videos", []))
        seen = {v.get("videoId") for v in videos}
        total = result.get("videoCount") or 0
        page = 2
        while len(videos) < total and page <= MAX_PLAYLIST_PAGES:
            more = self._get(f"/playlists/{playlist_id}", page=page).get("videos", [])
            new = [v for v in more if v.get("videoId") not in seen]
            if not new:
                break
            videos.extend(new)
            seen.update(v.get("videoId") for v in new)
            page += 1
        result["videos"] = videos

        self._cache.set(key, result)
        return result

    def channel(self, channel_id: str) -> dict[str, Any]:
        return self._cached(f"channel:{channel_id}", f"/channels/{channel_id}")

    def channel_videos(self, channel_id: str) -> list[dict[str, Any]]:
        result = self._cached(
            f"channel_videos:{channel_id}", f"/channels/{channel_id}/videos"
        )
        return result.get("videos", [])

    def stream_url(self, video_id: str, itag: str) -> str:
        """Stable, non-expiring audio URL.

        ``/latest_version`` resolves a fresh signed stream on every request and
        redirects to it; ``local=true`` makes Invidious proxy the bytes, so
        GStreamer never talks to googlevideo.com directly.
        """
        query = urllib.parse.urlencode({"id": video_id, "itag": itag, "local": "true"})
        return f"{self.base_url}/latest_version?{query}"


def _error_detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("error", response.text))[:200]
    except ValueError:
        return response.text[:200]
