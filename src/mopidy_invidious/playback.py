from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mopidy import backend
from mopidy.types import Uri

from . import uris
from .client import InvidiousError

if TYPE_CHECKING:
    from mopidy.audio import AudioProxy

    from .backend import InvidiousBackend

logger = logging.getLogger(__name__)


class InvidiousPlaybackProvider(backend.PlaybackProvider):
    def __init__(
        self, audio: AudioProxy, backend: InvidiousBackend, config: dict[str, Any]
    ) -> None:
        super().__init__(audio, backend)
        self.client = backend.client
        self.preferred_itags = [str(i) for i in config["audio_itags"]]

    def translate_uri(self, uri: Uri) -> Uri | None:
        try:
            parsed = uris.parse(uri)
        except ValueError:
            logger.warning("Cannot play %s: invalid URI", uri)
            return None
        if parsed.kind != uris.VIDEO:
            return None

        try:
            video = self.client.video(parsed.id)
        except InvidiousError as exc:
            # Don't give up: latest_version can still work for the usual itag.
            logger.warning("Metadata for %s unavailable (%s), guessing", uri, exc)
            return Uri(self.client.stream_url(parsed.id, self.preferred_itags[0]))

        if video.get("liveNow") and video.get("hlsUrl"):
            return Uri(video["hlsUrl"])

        itag = self._pick_itag(video)
        if itag is None:
            logger.warning("No audio stream found for %s", uri)
            return None
        logger.debug("Playing %s using itag %s", uri, itag)
        return Uri(self.client.stream_url(parsed.id, itag))

    def _pick_itag(self, video: dict[str, Any]) -> str | None:
        available = [
            str(f.get("itag"))
            for f in video.get("adaptiveFormats", [])
            if str(f.get("type", "")).startswith("audio/")
        ]
        for itag in self.preferred_itags:
            if itag in available:
                return itag
        if available:
            return available[0]
        # Muxed audio+video stream as the last resort (itag 18 = 360p mp4).
        muxed = [str(f.get("itag")) for f in video.get("formatStreams", [])]
        return muxed[0] if muxed else None
