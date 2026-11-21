from __future__ import annotations

import configparser
import copy
from typing import Any

import pytest

from mopidy_invidious import Extension

# Trimmed-down copies of real Invidious 2026.08 API responses.
VIDEO: dict[str, Any] = {
    "type": "video",
    "title": "Daft Punk - One More Time (Official Video)",
    "videoId": "FGBhQbmPwH8",
    "author": "Daft Punk",
    "authorId": "UC_kRDKYrUlrbtrSiyu5Tflg",
    "lengthSeconds": 322,
    "published": 1191628800,
    "genre": "Music",
    "liveNow": False,
    "adaptiveFormats": [
        {"itag": "137", "type": 'video/mp4; codecs="avc1.640028"'},
        {"itag": "140", "type": 'audio/mp4; codecs="mp4a.40.2"'},
        {"itag": "249", "type": 'audio/webm; codecs="opus"'},
        {"itag": "251", "type": 'audio/webm; codecs="opus"'},
    ],
    "formatStreams": [{"itag": "18", "type": 'video/mp4; codecs="avc1, mp4a"'}],
}

TOPIC_VIDEO: dict[str, Any] = {
    "type": "video",
    "title": "Harder, Better, Faster, Stronger",
    "videoId": "GDpmVUEjagg",
    "author": "Daft Punk - Topic",
    "authorId": "UCz-a7lHpbHRZEVcBvOavkjQ",
    "lengthSeconds": 225,
}

PLAYLIST: dict[str, Any] = {
    "type": "playlist",
    "title": "Daft punk music story (in order)",
    "playlistId": "PLA95EFE7EDEF0514F",
    "playlistThumbnail": "https://i.ytimg.com/vi/FGBhQbmPwH8/hqdefault.jpg",
    "author": "Geo Teh Fluffy Wuffy",
    "authorId": "UCp5g0ULfFiVDkuKbsXSG9IA",
    "videoCount": 2,
    "videos": [VIDEO, TOPIC_VIDEO],
}

CHANNEL: dict[str, Any] = {
    "type": "channel",
    "author": "Daft Punk",
    "authorId": "UC_kRDKYrUlrbtrSiyu5Tflg",
    "authorVerified": True,
    "subCount": 7190000,
    "authorThumbnails": [{"url": "//yt3.ggpht.com/abc=s176", "width": 176}],
}


class FakeClient:
    base_url = "http://invidious-app:3000"

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.search_results: dict[str, list[dict[str, Any]]] = {
            "video": [VIDEO, TOPIC_VIDEO],
            "playlist": [PLAYLIST],
            "channel": [CHANNEL],
        }

    def video(self, video_id: str) -> dict[str, Any]:
        self.calls.append(("video", video_id))
        return copy.deepcopy(VIDEO)

    def playlist(self, playlist_id: str) -> dict[str, Any]:
        self.calls.append(("playlist", playlist_id))
        return copy.deepcopy(PLAYLIST)

    def channel(self, channel_id: str) -> dict[str, Any]:
        self.calls.append(("channel", channel_id))
        return copy.deepcopy(CHANNEL)

    def channel_videos(self, channel_id: str) -> list[dict[str, Any]]:
        self.calls.append(("channel_videos", channel_id))
        return [copy.deepcopy(VIDEO)]

    def search(
        self, query: str, *, type: str = "video", page: int = 1
    ) -> list[dict[str, Any]]:
        self.calls.append(("search", (query, type, page)))
        return copy.deepcopy(self.search_results[type]) if page == 1 else []

    def stream_url(self, video_id: str, itag: str) -> str:
        return f"{self.base_url}/latest_version?id={video_id}&itag={itag}&local=true"


class FakeBackend:
    def __init__(self, client: FakeClient) -> None:
        self.client = client


@pytest.fixture
def config() -> dict[str, Any]:
    ext = Extension()
    schema = ext.get_config_schema()
    raw = ext.get_default_config()
    # Parse the bundled ext.conf through the real schema.
    parser = configparser.RawConfigParser()
    parser.read_string(raw)
    return {
        key: schema[key].deserialize(value)
        for key, value in parser["invidious"].items()
    }


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def backend(client: FakeClient) -> FakeBackend:
    return FakeBackend(client)
