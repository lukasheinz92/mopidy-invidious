from __future__ import annotations

import logging
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from mopidy import backend
from mopidy.models import Image, Ref, SearchResult, Track

from . import ranking, translator
from . import uris as iuris
from .client import InvidiousError

if TYPE_CHECKING:
    from mopidy.types import Query, SearchField, Uri

    from .backend import InvidiousBackend

logger = logging.getLogger(__name__)

# Invidious returns ~20 videos per search page.
SEARCH_PAGE_SIZE = 20


class InvidiousLibraryProvider(backend.LibraryProvider):
    root_directory = Ref.directory(uri=iuris.ROOT, name="Invidious")

    def __init__(self, backend: InvidiousBackend, config: dict[str, Any]) -> None:
        super().__init__(backend)
        self.client = backend.client
        self.config = config
        self.parse_titles = config["parse_titles"]
        self.public_url = config["public_url"] or config["base_url"]
        self.track_limit = config["search_track_results"]
        if config.get("search_results") is not None:
            logger.warning(
                "invidious/search_results is deprecated, "
                "use invidious/search_track_results instead"
            )
            self.track_limit = config["search_results"]
        self._pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="invidious")

    # -- browse -------------------------------------------------------------

    def browse(self, uri: Uri) -> list[Ref]:
        try:
            parsed = iuris.parse(uri)
            if parsed.kind == "root":
                return self._browse_root()
            if uri == iuris.PLAYLISTS_DIR:
                return self._browse_playlists()
            if uri == iuris.CHANNELS_DIR:
                return self._browse_channels()
            if parsed.kind in (iuris.PLAYLIST, iuris.CHANNEL):
                return [translator.track_ref(t) for t in self.lookup(uri)]
        except (ValueError, InvidiousError) as exc:
            logger.warning("Failed to browse %s: %s", uri, exc)
        return []

    def _browse_root(self) -> list[Ref]:
        refs = []
        if self.config["playlists"]:
            refs.append(Ref.directory(uri=iuris.PLAYLISTS_DIR, name="Playlists"))
        if self.config["channels"]:
            refs.append(Ref.directory(uri=iuris.CHANNELS_DIR, name="Channels"))
        return refs

    def _browse_playlists(self) -> list[Ref]:
        refs = []
        for playlist_id in self.config["playlists"]:
            try:
                playlist = self.client.playlist(playlist_id)
            except InvidiousError as exc:
                logger.warning("Skipping playlist %s: %s", playlist_id, exc)
                continue
            refs.append(translator.album_ref(translator.playlist_to_album(playlist)))
        return refs

    def _browse_channels(self) -> list[Ref]:
        refs = []
        for channel_id in self.config["channels"]:
            try:
                channel = self.client.channel(channel_id)
            except InvidiousError as exc:
                logger.warning("Skipping channel %s: %s", channel_id, exc)
                continue
            refs.append(translator.artist_ref(translator.channel_to_artist(channel)))
        return refs

    # -- lookup -------------------------------------------------------------

    def lookup(self, uri: Uri) -> list[Track]:
        try:
            parsed = iuris.parse(uri)
            if parsed.kind == iuris.VIDEO:
                track = translator.video_to_track(
                    self.client.video(parsed.id), parse_titles=self.parse_titles
                )
                return [track] if track else []
            if parsed.kind == iuris.PLAYLIST:
                return translator.playlist_to_tracks(
                    self.client.playlist(parsed.id), parse_titles=self.parse_titles
                )
            if parsed.kind == iuris.CHANNEL:
                tracks = (
                    translator.video_to_track(v, parse_titles=self.parse_titles)
                    for v in self.client.channel_videos(parsed.id)
                )
                return [t for t in tracks if t is not None]
        except (ValueError, InvidiousError) as exc:
            logger.warning("Failed to look up %s: %s", uri, exc)
        return []

    # -- search -------------------------------------------------------------

    def search(
        self,
        query: Query[SearchField],
        uris: Iterable[Uri] | None = None,
        exact: bool = False,
    ) -> SearchResult | None:
        terms = [
            str(value)
            for field in ("any", "artist", "albumartist", "track_name", "album")
            for value in query.get(field, ())
        ]
        if not terms:
            return None
        q = " ".join(terms)

        playlist_limit = self.config["search_playlist_results"]
        channel_limit = self.config["search_channel_results"]

        videos = self._pool.submit(self._search_videos, q)
        playlists = (
            self._pool.submit(self._search, q, "playlist") if playlist_limit else None
        )
        channels = (
            self._pool.submit(self._search, q, "channel") if channel_limit else None
        )

        return SearchResult(
            uri=iuris.search(q),
            tracks=tuple(videos.result()),
            albums=tuple(
                translator.playlist_to_album(p)
                for p in ranking.pick_playlists(
                    playlists.result() if playlists else [], q, playlist_limit
                )
            ),
            artists=tuple(
                translator.channel_to_artist(c)
                for c in ranking.pick_channels(
                    channels.result() if channels else [], q, channel_limit
                )
            ),
        )

    def _search(self, q: str, type: str, page: int = 1) -> list[dict[str, Any]]:
        try:
            return self.client.search(q, type=type, page=page)
        except InvidiousError as exc:
            logger.warning("Invidious %s search for %r failed: %s", type, q, exc)
            return []

    def _search_videos(self, q: str) -> list[Track]:
        limit = self.track_limit
        tracks: list[Track] = []
        page = 1
        while len(tracks) < limit:
            results = self._search(q, "video", page)
            if not results:
                break
            for video in results:
                track = translator.video_to_track(video, parse_titles=self.parse_titles)
                if track is not None:
                    tracks.append(track)
            if len(results) < SEARCH_PAGE_SIZE:
                break
            page += 1
        return tracks[:limit]

    # -- images -------------------------------------------------------------

    def get_images(self, uris: Iterable[Uri]) -> dict[Uri, list[Image]]:
        result: dict[Uri, list[Image]] = {}
        for uri in uris:
            try:
                parsed = iuris.parse(uri)
                if parsed.kind == iuris.VIDEO:
                    result[uri] = translator.video_images(parsed.id, self.public_url)
                elif parsed.kind == iuris.PLAYLIST:
                    playlist = self.client.playlist(parsed.id)
                    thumb = playlist.get("playlistThumbnail")
                    result[uri] = translator.thumbnails_to_images(
                        [{"url": thumb}] if thumb else [], self.public_url
                    )
                elif parsed.kind == iuris.CHANNEL:
                    channel = self.client.channel(parsed.id)
                    result[uri] = translator.thumbnails_to_images(
                        channel.get("authorThumbnails", []), self.public_url
                    )
            except (ValueError, InvidiousError) as exc:
                logger.debug("No images for %s: %s", uri, exc)
        return result
