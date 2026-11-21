import pytest

from mopidy_invidious.ranking import name_matches_query, pick_channels, pick_playlists


@pytest.mark.parametrize(
    ("name", "query", "expected"),
    [
        ("Daft Punk", "daft punk", True),
        ("Daft Punk", "daft punk one more time", True),
        ("DaftPunkVEVO", "daft punk", True),
        ("Daft Punk - Topic", "Daft Punk", True),
        ("KRYŠTOF", "kryštof", True),
        ("Radiohead", "radiohead ok computer", True),
        ("Daft Spunky", "daft punk", False),
        ("Daft Punk Live", "daft punk", False),
        ("PODCAST ONE MORE TIME di Luca", "one more time", False),
        ("Kryštof Paleta", "kryštof", False),
        ("Punk", "daftpunk", False),
        ("VEVO", "vevo", True),
        ("", "anything", False),
    ],
)
def test_name_matches_query(name, query, expected):
    assert name_matches_query(name, query) is expected


def _channel(author, verified=False, subs=50_000):
    return {
        "type": "channel",
        "author": author,
        "authorId": f"UC{author}",
        "authorVerified": verified,
        "subCount": subs,
    }


def test_pick_channels_drops_tiny_unverified_namesakes():
    channels = [
        _channel("Radiohead", verified=True, subs=0),
        _channel("OK COMPUTER", subs=4),
    ]
    picked = pick_channels(channels, "radiohead ok computer", limit=3)
    assert [c["author"] for c in picked] == ["Radiohead"]


def test_pick_channels_filters_ranks_and_dedupes():
    channels = [
        _channel("Daft Punk - Topic"),
        _channel("DaftPunkVEVO", verified=False),
        _channel("Daft Punk", verified=True),
        _channel("Daft Spunky", verified=True),
        _channel("Daft Punk Live Covers"),
    ]
    picked = pick_channels(channels, "daft punk", limit=3)
    # Verified "Daft Punk" wins; VEVO is a duplicate of the same artist name.
    assert [c["author"] for c in picked] == ["Daft Punk"]


def test_pick_channels_limit():
    channels = [_channel("A B"), _channel("C D")]
    assert len(pick_channels(channels, "a b c d", limit=1)) == 1
    assert pick_channels(channels, "a b c d", limit=0) == []


def _playlist(title, author, pid):
    return {"type": "playlist", "title": title, "author": author, "playlistId": pid}


def test_pick_playlists_prefers_official_then_albums():
    playlists = [
        _playlist("Best Of Daft Punk", "misterepicpants", "PL1"),
        _playlist("Daft Punk - Discovery (Full Album)", "fan", "PL2"),
        _playlist("Daft Punk Essentials", "Daft Punk", "PL3"),
        _playlist("Greatest Hits", "DaftPunkVEVO", "PL4"),
        {"type": "video", "title": "album"},
    ]
    picked = pick_playlists(playlists, "daft punk", limit=5)
    assert [p["playlistId"] for p in picked] == ["PL3", "PL4", "PL2"]
    assert len(pick_playlists(playlists, "daft punk", limit=2)) == 2
