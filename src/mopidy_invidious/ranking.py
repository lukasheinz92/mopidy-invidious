"""Pick the few channels and playlists worth showing above search tracks.

Invidious returns ~20 channels and ~20 playlists per search, mostly fan
uploads and namesakes. We keep only results whose channel name is (part of)
what the user typed, e.g. "daft punk" keeps "Daft Punk" and "DaftPunkVEVO"
but not "Daft Spunky" or "Daft Punk Live Covers".
"""

from __future__ import annotations

import re
from typing import Any

from .translator import TOPIC_SUFFIX

_TOKEN = re.compile(r"\w+")
_NAME_NOISE = ("vevo", "official", "music")
# Unverified channels below this are almost always namesakes, not artists.
MIN_SUBSCRIBERS = 1000


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.casefold())


def _squash(tokens: list[str]) -> str:
    joined = "".join(tokens)
    for noise in _NAME_NOISE:
        if joined.endswith(noise) and len(joined) > len(noise):
            joined = joined.removesuffix(noise)
    return joined


def name_matches_query(name: str, query: str) -> bool:
    """True if ``name`` equals a contiguous run of words in ``query``.

    Spacing and a trailing "VEVO"/"Official"/"Music" are ignored, so
    "DaftPunkVEVO" matches the query "daft punk one more time".
    """
    name_key = _squash(_tokens(name.removesuffix(TOPIC_SUFFIX)))
    if len(name_key) < 2:
        return False
    words = _tokens(query)
    return any(
        "".join(words[i:j]) == name_key
        for i in range(len(words))
        for j in range(i + 1, len(words) + 1)
    )


def pick_channels(
    channels: list[dict[str, Any]], query: str, limit: int
) -> list[dict[str, Any]]:
    candidates = [
        c
        for c in channels
        if c.get("type") == "channel"
        and c.get("authorId")
        # Topic channels can't list their videos (Invidious returns HTTP 500).
        and not (c.get("author") or "").endswith(TOPIC_SUFFIX)
        and (c.get("authorVerified") or (c.get("subCount") or 0) >= MIN_SUBSCRIBERS)
        and name_matches_query(c.get("author") or "", query)
    ]
    # Stable sort: verified first, otherwise keep YouTube's relevance order.
    candidates.sort(key=lambda c: not c.get("authorVerified"))

    picked, seen = [], set()
    for channel in candidates:
        key = _squash(_tokens(channel["author"]))
        if key not in seen:
            seen.add(key)
            picked.append(channel)
    return picked[:limit]


def pick_playlists(
    playlists: list[dict[str, Any]], query: str, limit: int
) -> list[dict[str, Any]]:
    official, albums = [], []
    for playlist in playlists:
        if playlist.get("type") != "playlist" or not playlist.get("playlistId"):
            continue
        if name_matches_query(playlist.get("author") or "", query):
            official.append(playlist)
        elif "album" in (playlist.get("title") or "").casefold():
            albums.append(playlist)
    return (official + albums)[:limit]
