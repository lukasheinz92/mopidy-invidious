from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

import pykka
from mopidy import backend, httpclient
from mopidy.types import UriScheme

from . import Extension
from .client import InvidiousClient, InvidiousError
from .library import InvidiousLibraryProvider
from .playback import InvidiousPlaybackProvider

if TYPE_CHECKING:
    from mopidy.audio import AudioProxy
    from mopidy.config import Config

logger = logging.getLogger(__name__)


class InvidiousBackend(pykka.ThreadingActor, backend.Backend):
    uri_schemes: ClassVar[list[UriScheme]] = [UriScheme("invidious")]

    def __init__(self, config: Config, audio: AudioProxy) -> None:
        super().__init__()
        ext_config = config["invidious"]

        self.client = InvidiousClient(
            ext_config["base_url"],
            timeout=ext_config["timeout"],
            user_agent=httpclient.format_user_agent(
                f"{Extension.dist_name}/{Extension.version}"
            ),
            proxy=httpclient.format_proxy(config["proxy"]),
            cache_ttl=ext_config["cache_ttl"],
        )
        self.library = InvidiousLibraryProvider(backend=self, config=ext_config)
        self.playback = InvidiousPlaybackProvider(
            audio=audio, backend=self, config=ext_config
        )

    def on_start(self) -> None:
        try:
            stats = self.client.stats()
        except InvidiousError as exc:
            # Invidious may simply be starting up; requests will be retried
            # lazily, so don't take the whole of Mopidy down.
            logger.warning(
                "Invidious at %s not reachable: %s", self.client.base_url, exc
            )
            return
        software = stats.get("software", {})
        logger.info(
            "Connected to %s %s at %s",
            software.get("name", "Invidious"),
            software.get("version", "?"),
            self.client.base_url,
        )

    def on_stop(self) -> None:
        self.client.close()
