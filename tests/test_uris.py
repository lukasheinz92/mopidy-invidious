import pytest

from mopidy_invidious import uris


def test_roundtrip_video():
    uri = uris.video("FGBhQbmPwH8")
    assert uri == "invidious:video:FGBhQbmPwH8"
    assert uris.parse(uri) == ("video", "FGBhQbmPwH8")


def test_parse_playlist_and_channel():
    assert uris.parse("invidious:playlist:PLA95EFE7EDEF0514F").kind == "playlist"
    assert uris.parse("invidious:channel:UC_kRDKYrUlrbtrSiyu5Tflg").kind == "channel"


def test_parse_root_and_directories():
    assert uris.parse(uris.ROOT).kind == "root"
    assert uris.parse(uris.PLAYLISTS_DIR) == ("directory", "playlists")


@pytest.mark.parametrize(
    "uri",
    [
        "youtube:video:FGBhQbmPwH8",
        "invidious:video:short",
        "invidious:video:../../etc/passwd",
        "invidious:channel:notachannel",
        "invidious:unknown:abc",
        "invidious:",
    ],
)
def test_parse_rejects_bad_uris(uri):
    with pytest.raises(ValueError):
        uris.parse(uri)


def test_search_uri_is_quoted():
    assert uris.search("daft punk") == "invidious:search:daft%20punk"
