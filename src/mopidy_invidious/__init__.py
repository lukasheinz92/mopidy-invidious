from __future__ import annotations

import pathlib
from importlib.metadata import version

from mopidy import config, ext

__version__ = version("mopidy-invidious")


class Extension(ext.Extension):
    dist_name = "mopidy-invidious"
    ext_name = "invidious"
    version = __version__

    def get_default_config(self) -> str:
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self) -> config.ConfigSchema:
        schema = super().get_config_schema()
        schema["base_url"] = config.String()
        schema["public_url"] = config.String(optional=True)
        schema["timeout"] = config.Integer(minimum=1, maximum=120)
        schema["search_track_results"] = config.Integer(minimum=0, maximum=200)
        # Deprecated alias of search_track_results; still honoured if set.
        schema["search_results"] = config.Integer(optional=True, minimum=0, maximum=200)
        schema["search_playlist_results"] = config.Integer(minimum=0, maximum=20)
        schema["search_channel_results"] = config.Integer(minimum=0, maximum=20)
        schema["search_playlists"] = config.Deprecated()
        schema["search_channels"] = config.Deprecated()
        schema["audio_itags"] = config.List()
        schema["parse_titles"] = config.Boolean()
        schema["playlists"] = config.List(optional=True)
        schema["channels"] = config.List(optional=True)
        schema["cache_ttl"] = config.Integer(minimum=0)
        return schema

    def setup(self, registry: ext.Registry) -> None:
        from .backend import InvidiousBackend

        registry.add("backend", InvidiousBackend)
