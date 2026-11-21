import pytest

from mopidy_invidious import uris
from mopidy_invidious.client import InvidiousClient, InvidiousError
from mopidy_invidious.playback import InvidiousPlaybackProvider

from .conftest import VIDEO


@pytest.fixture
def playback(backend, config):
    return InvidiousPlaybackProvider(audio=None, backend=backend, config=config)


def test_translate_uri_prefers_opus(playback):
    url = playback.translate_uri(uris.video("FGBhQbmPwH8"))
    assert url == (
        "http://invidious-app:3000/latest_version?id=FGBhQbmPwH8&itag=251&local=true"
    )


def test_translate_uri_falls_back_to_next_preferred_itag(playback, client):
    formats = [f for f in VIDEO["adaptiveFormats"] if f["itag"] != "251"]
    client.video = lambda _: {**VIDEO, "adaptiveFormats": formats}
    assert "itag=140" in playback.translate_uri(uris.video("FGBhQbmPwH8"))


def test_translate_uri_uses_muxed_stream_without_audio_formats(playback, client):
    client.video = lambda _: {**VIDEO, "adaptiveFormats": []}
    assert "itag=18" in playback.translate_uri(uris.video("FGBhQbmPwH8"))


def test_translate_uri_guesses_when_metadata_fails(playback, client):
    def fail(_):
        raise InvidiousError("boom")

    client.video = fail
    assert "itag=251" in playback.translate_uri(uris.video("FGBhQbmPwH8"))


def test_translate_uri_live_stream_uses_hls(playback, client):
    client.video = lambda _: {**VIDEO, "liveNow": True, "hlsUrl": "http://x/m.m3u8"}
    assert playback.translate_uri(uris.video("FGBhQbmPwH8")) == "http://x/m.m3u8"


def test_translate_uri_rejects_non_videos(playback):
    assert playback.translate_uri(uris.playlist("PLA95EFE7EDEF0514F")) is None
    assert playback.translate_uri("invidious:video:bad") is None


def test_client_stream_url():
    client = InvidiousClient("http://invidious-app:3000/")
    try:
        assert client.stream_url("abcdefghijk", "140") == (
            "http://invidious-app:3000/latest_version"
            "?id=abcdefghijk&itag=140&local=true"
        )
    finally:
        client.close()
