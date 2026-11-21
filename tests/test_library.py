import pytest

from mopidy_invidious import uris
from mopidy_invidious.client import InvidiousError
from mopidy_invidious.library import InvidiousLibraryProvider

from .conftest import PLAYLIST


@pytest.fixture
def library(backend, config):
    config["public_url"] = "https://invidious.example"
    config["playlists"] = ("PLA95EFE7EDEF0514F",)
    return InvidiousLibraryProvider(backend=backend, config=config)


def test_browse_root_only_lists_configured_directories(library):
    refs = library.browse(uris.ROOT)
    assert [r.uri for r in refs] == [uris.PLAYLISTS_DIR]


def test_browse_playlists(library):
    (ref,) = library.browse(uris.PLAYLISTS_DIR)
    assert ref.type == "album"
    assert ref.uri == "invidious:playlist:PLA95EFE7EDEF0514F"


def test_browse_playlist_lists_tracks(library):
    refs = library.browse(uris.playlist("PLA95EFE7EDEF0514F"))
    assert [r.name for r in refs] == [
        "Daft Punk - One More Time",
        "Daft Punk - Harder, Better, Faster, Stronger",
    ]


def test_lookup_video(library):
    (track,) = library.lookup(uris.video("FGBhQbmPwH8"))
    assert track.name == "One More Time"


def test_lookup_invalid_uri_returns_empty(library):
    assert library.lookup("invidious:video:nope") == []


def test_lookup_api_error_returns_empty(library, client):
    def fail(_):
        raise InvidiousError("boom")

    client.video = fail
    assert library.lookup(uris.video("FGBhQbmPwH8")) == []


def test_search_combines_videos_playlists_channels(library, client):
    official = {
        **PLAYLIST,
        "playlistId": "PLSdoVPM5WnndLX6NgmbNi",
        "author": "Daft Punk",
    }
    client.search_results["playlist"] = [PLAYLIST, official]
    result = library.search({"artist": ["daft punk"], "track_name": ["one more time"]})
    assert result.uri == "invidious:search:daft%20punk%20one%20more%20time"
    assert len(result.tracks) == 2
    # The fan playlist ("Geo Teh Fluffy Wuffy", no "album") is filtered out.
    assert [a.uri for a in result.albums] == [
        "invidious:playlist:PLSdoVPM5WnndLX6NgmbNi"
    ]
    assert [a.name for a in result.artists] == ["Daft Punk"]
    assert ("search", ("daft punk one more time", "video", 1)) in client.calls


def test_search_respects_limits(library, client):
    library.track_limit = 1
    library.config["search_playlist_results"] = 0
    library.config["search_channel_results"] = 0
    result = library.search({"any": ["x"]})
    assert len(result.tracks) == 1
    assert result.albums == () and result.artists == ()
    assert {c[1][1] for c in client.calls} == {"video"}


def test_track_limit_from_config(backend, config):
    config["search_track_results"] = 7
    assert InvidiousLibraryProvider(backend=backend, config=config).track_limit == 7


def test_deprecated_search_results_overrides(backend, config, caplog):
    config["search_track_results"] = 7
    config["search_results"] = 3
    library = InvidiousLibraryProvider(backend=backend, config=config)
    assert library.track_limit == 3
    assert "search_results is deprecated" in caplog.text


def test_search_empty_query(library):
    assert library.search({}) is None


def test_get_images_video_needs_no_api_call(library, client):
    uri = uris.video("FGBhQbmPwH8")
    images = library.get_images([uri])[uri]
    assert images[0].uri == "https://invidious.example/vi/FGBhQbmPwH8/mqdefault.jpg"
    assert client.calls == []
