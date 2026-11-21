import pytest

from mopidy_invidious import translator

from .conftest import CHANNEL, PLAYLIST, TOPIC_VIDEO, VIDEO


@pytest.mark.parametrize(
    ("title", "author", "expected"),
    [
        (
            "Daft Punk - One More Time (Official Video)",
            "Daft Punk",
            ("Daft Punk", "One More Time"),
        ),
        ("Around the World", "Daft Punk - Topic", ("Daft Punk", "Around the World")),
        ("Some Mix [HD]", "DJ Channel", ("DJ Channel", "Some Mix")),
        ("Artist – Song (Lyrics)", "Uploader", ("Artist", "Song")),  # noqa: RUF001
        ("No separator here", "Uploader", ("Uploader", "No separator here")),
    ],
)
def test_split_title(title, author, expected):
    assert translator.split_title(title, author) == expected


def test_split_title_disabled():
    assert translator.split_title("A - B", "Chan", parse=False) == ("Chan", "A - B")


def test_video_to_track():
    track = translator.video_to_track(VIDEO)
    assert track is not None
    assert track.uri == "invidious:video:FGBhQbmPwH8"
    assert track.name == "One More Time"
    assert track.length == 322_000
    assert track.genre == "Music"
    assert track.date == "2007-10-06"
    (artist,) = track.artists
    assert artist.name == "Daft Punk"
    assert artist.uri == "invidious:channel:UC_kRDKYrUlrbtrSiyu5Tflg"


def test_video_to_track_artist_differs_from_uploader():
    video = {**VIDEO, "author": "Some Uploader"}
    track = translator.video_to_track(video)
    (artist,) = track.artists
    assert artist.name == "Daft Punk"
    assert artist.uri is None


def test_video_to_track_skips_non_videos():
    assert translator.video_to_track(PLAYLIST) is None
    assert translator.video_to_track({"type": "video"}) is None


def test_playlist_to_tracks():
    tracks = translator.playlist_to_tracks(PLAYLIST)
    assert [t.track_no for t in tracks] == [1, 2]
    assert all(t.album.uri == "invidious:playlist:PLA95EFE7EDEF0514F" for t in tracks)
    assert tracks[1].name == TOPIC_VIDEO["title"]


def test_channel_to_artist():
    artist = translator.channel_to_artist(CHANNEL)
    assert artist.uri == "invidious:channel:UC_kRDKYrUlrbtrSiyu5Tflg"
    assert artist.name == "Daft Punk"


def test_thumbnails_to_images_absolutizes_urls():
    images = translator.thumbnails_to_images(
        [{"url": "//yt3.ggpht.com/a"}, {"url": "/vi/x/1.jpg"}, {"url": ""}],
        "https://inv.example/",
    )
    assert [i.uri for i in images] == [
        "https://yt3.ggpht.com/a",
        "https://inv.example/vi/x/1.jpg",
    ]
