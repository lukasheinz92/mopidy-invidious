"""Mopidy URI scheme for Invidious.

invidious:root                      browse root
invidious:directory:playlists       configured playlists
invidious:directory:channels        configured channels
invidious:video:<videoId>           a single video -> Track
invidious:playlist:<playlistId>     a playlist -> Album
invidious:channel:<channelId>       a channel -> Artist
invidious:search:<query>            search result
"""

from __future__ import annotations

import re
import urllib.parse
from typing import NamedTuple

from mopidy.types import Uri

SCHEME = "invidious"

ROOT = Uri(f"{SCHEME}:root")
PLAYLISTS_DIR = Uri(f"{SCHEME}:directory:playlists")
CHANNELS_DIR = Uri(f"{SCHEME}:directory:channels")

VIDEO = "video"
PLAYLIST = "playlist"
CHANNEL = "channel"
DIRECTORY = "directory"
SEARCH = "search"

_ID_PATTERNS = {
    VIDEO: re.compile(r"^[A-Za-z0-9_-]{11}$"),
    PLAYLIST: re.compile(r"^[A-Za-z0-9_-]{10,64}$"),
    CHANNEL: re.compile(r"^UC[A-Za-z0-9_-]{22}$"),
}


class ParsedUri(NamedTuple):
    kind: str
    id: str


def video(video_id: str) -> Uri:
    return Uri(f"{SCHEME}:{VIDEO}:{video_id}")


def playlist(playlist_id: str) -> Uri:
    return Uri(f"{SCHEME}:{PLAYLIST}:{playlist_id}")


def channel(channel_id: str) -> Uri:
    return Uri(f"{SCHEME}:{CHANNEL}:{channel_id}")


def search(query: str) -> Uri:
    return Uri(f"{SCHEME}:{SEARCH}:{urllib.parse.quote(query)}")


def parse(uri: str) -> ParsedUri:
    """Split an ``invidious:`` URI into its kind and ID.

    Raises ``ValueError`` for anything that is not a well-formed URI.
    """
    scheme, _, rest = uri.partition(":")
    kind, _, ident = rest.partition(":")
    if scheme != SCHEME or not kind:
        msg = f"Not an {SCHEME} URI: {uri!r}"
        raise ValueError(msg)
    if kind == "root" and not ident:
        return ParsedUri(kind, "")
    pattern = _ID_PATTERNS.get(kind)
    if pattern is not None and not pattern.match(ident):
        msg = f"Invalid {kind} ID in URI: {uri!r}"
        raise ValueError(msg)
    if kind not in (*_ID_PATTERNS, DIRECTORY, SEARCH):
        msg = f"Unknown {SCHEME} URI kind: {uri!r}"
        raise ValueError(msg)
    return ParsedUri(kind, ident)
