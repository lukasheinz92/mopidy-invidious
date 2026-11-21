"""Convert Invidious API JSON into Mopidy models."""

from __future__ import annotations

import datetime
import re
from typing import Any

from mopidy.models import Album, Artist, Image, Ref, Track
from mopidy.types import DurationMs, ReleaseDate, Uri

from . import uris

TOPIC_SUFFIX = " - Topic"
_TITLE_SEPARATORS = re.compile(r"\s+[-–—]\s+")  # noqa: RUF001 - hyphen, en/em dash
_TITLE_NOISE = re.compile(
    r"\s*[\(\[](official\s+(music\s+)?(video|audio|lyric\s+video|visualizer)|"
    r"lyrics?|audio|hd|hq|4k|remastered(\s+\d{4})?)[\)\]]\s*",
    re.IGNORECASE,
)


def clean_author(author: str) -> str:
    """'Daft Punk - Topic' (YouTube Music auto channel) -> 'Daft Punk'."""
    return author.removesuffix(TOPIC_SUFFIX)


def split_title(title: str, author: str, *, parse: bool = True) -> tuple[str, str]:
    """Return ``(artist, track_name)`` for a video.

    Auto-generated "<artist> - Topic" channels already have a clean title and
    a reliable artist. Otherwise try the common "Artist - Title" convention and
    fall back to the channel name.
    """
    artist = clean_author(author)
    if not parse or author.endswith(TOPIC_SUFFIX):
        return artist, title

    parts = _TITLE_SEPARATORS.split(title, maxsplit=1)
    if len(parts) == 2 and all(p.strip() for p in parts):
        artist, title = parts
    title = _TITLE_NOISE.sub(" ", title).strip() or title
    return artist.strip(), title.strip()


def _release_date(published: int | None) -> ReleaseDate | None:
    if not published:
        return None
    date = datetime.datetime.fromtimestamp(published, tz=datetime.UTC).date()
    return ReleaseDate(date.isoformat())


def video_to_track(
    video: dict[str, Any],
    *,
    album: Album | None = None,
    track_no: int | None = None,
    parse_titles: bool = True,
) -> Track | None:
    video_id = video.get("videoId")
    if not video_id or video.get("type", "video") != "video":
        return None

    author = video.get("author") or ""
    artist_name, name = split_title(
        video.get("title") or video_id, author, parse=parse_titles
    )
    channel_uri = uris.channel(video["authorId"]) if video.get("authorId") else None
    # Only link the artist to the channel when the artist *is* the channel.
    artist = Artist(
        uri=channel_uri if artist_name == clean_author(author) else None,
        name=artist_name or None,
    )
    length = video.get("lengthSeconds")

    return Track(
        uri=uris.video(video_id),
        name=name,
        artists=frozenset({artist}) if artist.name else frozenset(),
        album=album,
        track_no=track_no,
        genre=video.get("genre") or None,
        length=DurationMs(length * 1000) if length else None,
        date=_release_date(video.get("published")),
        comment=f"https://www.youtube.com/watch?v={video_id}",
    )


def playlist_to_album(playlist: dict[str, Any]) -> Album:
    author = playlist.get("author")
    return Album(
        uri=uris.playlist(playlist["playlistId"]),
        name=playlist.get("title"),
        artists=frozenset({Artist(name=clean_author(author))})
        if author
        else frozenset(),
        num_tracks=playlist.get("videoCount") or None,
    )


def playlist_to_tracks(
    playlist: dict[str, Any], *, parse_titles: bool = True
) -> list[Track]:
    album = playlist_to_album(playlist)
    tracks = (
        video_to_track(v, album=album, track_no=i, parse_titles=parse_titles)
        for i, v in enumerate(playlist.get("videos", []), start=1)
    )
    return [t for t in tracks if t is not None]


def channel_to_artist(channel: dict[str, Any]) -> Artist:
    return Artist(
        uri=uris.channel(channel["authorId"]),
        name=clean_author(channel.get("author") or channel["authorId"]),
    )


def track_ref(track: Track) -> Ref:
    return Ref.track(uri=track.uri, name=_display_name(track))


def album_ref(album: Album) -> Ref:
    assert album.uri is not None
    return Ref.album(uri=album.uri, name=album.name)


def artist_ref(artist: Artist) -> Ref:
    assert artist.uri is not None
    return Ref.artist(uri=artist.uri, name=artist.name)


def _display_name(track: Track) -> str | None:
    artists = ", ".join(sorted(a.name for a in track.artists if a.name))
    return f"{artists} - {track.name}" if artists else track.name


def thumbnails_to_images(
    thumbnails: list[dict[str, Any]], base_url: str
) -> list[Image]:
    images = []
    for thumb in thumbnails:
        url = thumb.get("url")
        if not url:
            continue
        if url.startswith("//"):
            url = f"https:{url}"
        elif url.startswith("/"):
            url = f"{base_url.rstrip('/')}{url}"
        images.append(
            Image(
                uri=Uri(url),
                width=thumb.get("width") or None,
                height=thumb.get("height") or None,
            )
        )
    return images


def video_images(video_id: str, base_url: str) -> list[Image]:
    """Thumbnails served by Invidious' /vi/ proxy, without an API round trip."""
    base = base_url.rstrip("/")
    return [
        Image(uri=Uri(f"{base}/vi/{video_id}/mqdefault.jpg"), width=320, height=180),
        Image(uri=Uri(f"{base}/vi/{video_id}/hqdefault.jpg"), width=480, height=360),
    ]
