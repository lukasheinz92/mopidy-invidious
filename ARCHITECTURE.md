# Architecture

Mopidy-Invidious is a Mopidy 4 **backend extension**. It exposes a self-hosted
Invidious instance as a music library (browse / search / lookup) and plays its
audio through Mopidy's normal GStreamer pipeline.

## Deployment context

```
                       Docker network: nginx-proxy-manager_default
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                                                                          │
 │  ┌────────────────────────┐  /api/v1/*        ┌───────────────────────┐  │
 │  │ mopidy                 │──────────────────▶│ invidious-app :3000   │  │
 │  │  └ mopidy_invidious    │  /latest_version  │                       │  │
 │  │      (backend actor)   │──────┐ 302 ──────▶│ /companion/videoplay… │  │
 │  │  GStreamer playbin ◀───┘ audio bytes ◀─────│        │              │  │
 │  └──────────┬─────────────┘                   └────────┼──────────────┘  │
 │             │ PCM 48k/16/2                             ▼                 │
 │             ▼                                 ┌───────────────────────┐  │
 │  ┌────────────────────────┐                   │ invidious-companion   │──┼──▶ YouTube
 │  │ snapserver (snapfifo)  │──▶ Snapcast       │ :8282                 │  │
 │  └────────────────────────┘    clients        └───────────────────────┘  │
 └──────────────────────────────────────────────────────────────────────────┘
   Mopidy clients (Iris, Mobile, MPD) load cover art from public_url
   (https://invidious.example.org/vi/<id>/…) through nginx-proxy-manager.
```

Two Invidious URLs are configured on purpose:

| Setting      | Used by                     | Example value                            |
|--------------|-----------------------------|------------------------------------------|
| `base_url`   | Mopidy itself (API + audio) | `http://invidious-app:3000`              |
| `public_url` | Mopidy *clients* (images)   | `https://invidious.example.org`     |

Audio never leaves the Docker network, and Mopidy never contacts YouTube
directly.

## Modules

```
src/mopidy_invidious/
├── __init__.py    Extension: config schema, registers the backend
├── ext.conf       default config
├── backend.py     InvidiousBackend (pykka ThreadingActor), builds the client,
│                  logs the Invidious version on start (non-fatal if down)
├── client.py      InvidiousClient: httpx wrapper for /api/v1, TTL cache,
│                  playlist pagination, stream_url()
├── uris.py        URI scheme: build / parse / validate
├── translator.py  Invidious JSON → Mopidy models (Track/Album/Artist/Ref/Image)
├── library.py     LibraryProvider: browse, lookup, search, get_images
└── playback.py    PlaybackProvider: translate_uri → playable stream URL
```

Dependency direction: `backend → library/playback → client + translator → uris`.
`translator` and `uris` are pure functions (no I/O), which keeps most logic
unit-testable without Invidious.

## URI scheme

| URI                               | Mopidy model | Source endpoint                    |
|-----------------------------------|--------------|------------------------------------|
| `invidious:root`                  | directory    | config                             |
| `invidious:directory:playlists`   | directory    | `playlists` config                 |
| `invidious:directory:channels`    | directory    | `channels` config                  |
| `invidious:video:<videoId>`       | Track        | `/api/v1/videos/<id>`              |
| `invidious:playlist:<playlistId>` | Album        | `/api/v1/playlists/<id>` (paged)   |
| `invidious:channel:<UC…>`         | Artist       | `/api/v1/channels/<id>/videos`     |
| `invidious:search:<query>`        | SearchResult | `/api/v1/search?type=video\|playlist\|channel` |

IDs are validated with regexes before they are interpolated into API paths.

### Mapping YouTube → music metadata

* `Artist - Title (Official Video)` → artist `Artist`, track `Title` (common
  suffixes like *(Official Video)*, *[HD]*, *(Lyrics)* are stripped).
  Can be disabled with `parse_titles = false`.
* Auto-generated `<Artist> - Topic` channels (YouTube Music uploads) are
  trusted as-is: artist = channel name without ` - Topic`, track = title.
* The artist links to `invidious:channel:<id>` only when it is the uploading
  channel, so "browse artist" never lands on a random re-uploader.
* A playlist becomes an album; its videos get `track_no` in playlist order.

### Search ranking (`ranking.py`)

Invidious returns ~20 channels and ~20 playlists per query, mostly fan
uploads and namesakes, and many clients list them *above* the tracks. So only
a few are kept:

* **Channels** (`search_channel_results`, default 3): the channel name must
  equal a contiguous run of query words, ignoring case, spacing and a
  trailing *VEVO/Official/Music*. "daft punk" keeps *Daft Punk* and
  *DaftPunkVEVO*, but not *Daft Spunky* or *Daft Punk Live*. Unverified
  channels need at least 1,000 subscribers. Verified channels come first,
  and channels with the same name are deduplicated.
  `- Topic` channels are dropped because Invidious can't list their videos
  (HTTP 500).
* **Playlists** (`search_playlist_results`, default 5): first, official ones
  (the author matches the query the same way), then ones whose title
  contains "album". Everything else is dropped.

YouTube Music album playlists (`OLAK5uy_…`) would be ideal, but Invidious'
playlist search never returns them.

## Playback: why `/latest_version`

YouTube stream URLs are signed and expire after a few hours, and are bound to
the IP that requested them. A track can sit in Mopidy's tracklist for longer
than that. So `translate_uri` does **not** hand GStreamer a `googlevideo.com`
URL. It returns:

```
{base_url}/latest_version?id=<videoId>&itag=<itag>&local=true
```

Invidious resolves a fresh stream on every request and answers with a redirect
to its own `/companion/videoplayback` proxy. The URL never expires, works with
HTTP range requests (seeking), and keeps all traffic inside the instance.

The `itag` is picked from `audio_itags` (default `251, 140, 250, 249`: Opus
160k, AAC 128k, Opus 70k, Opus 50k) based on the `adaptiveFormats` the video
actually offers. That metadata usually comes from the cache filled by `lookup`
when the track was added. Fallbacks:
* metadata request fails → guess the first preferred itag
* no audio-only formats → muxed `formatStreams` (e.g. itag 18)
* live streams → `hlsUrl`

Opus at 48 kHz matches the Snapcast FIFO's sample format, so no resampling is
needed.

## Concurrency & caching

* The backend is a pykka `ThreadingActor`; Mopidy core calls into it serially.
* `search` runs its video, playlist, and channel queries in parallel on a
  small `ThreadPoolExecutor` (about 0.7 s on the Pi instead of 3 round trips).
* `httpx.Client` is shared and thread-safe; `_TTLCache` (lock-protected,
  `cache_ttl` seconds, bounded size) caches video, playlist, and channel
  responses. Clients like Iris call `lookup` and `get_images` repeatedly, so
  this matters.
* Video cover art is built from the ID (`/vi/<id>/mqdefault.jpg`) and needs no
  API call.

## Error handling

All API failures surface as `InvidiousError`. Library methods catch them, log
them, and return empty results, so a flaky Invidious never crashes Mopidy or
breaks other backends' search results. An unreachable Invidious at startup is
a warning, not a `BackendError`.

## Testing

* `tests/`: unit tests with a `FakeClient` using fixtures copied from real
  Invidious 2026.08 responses.
* `dev/remote.sh test`: runs them inside the production `mopidy:latest` image
  (Python 3.13 + GStreamer + Mopidy 4.0.2) on the Pi. PyGObject isn't
  practical on Windows.
* `dev/remote.sh e2e`: starts an **isolated** Mopidy (`mopidy-invidious-dev`,
  no published ports, `fakesink` output, other extensions disabled) on the
  Invidious network and runs `dev/e2e.py`: browse → search → images → lookup →
  play → seek.

## Roadmap

1. **MVP (done):** search, lookup, browse configured playlists/channels, playback, seek.
2. **Production rollout:** install in `multiroom-audio/mopidy/Dockerfile`
   (`pip install git+https://github.com/<user>/mopidy-invidious@vX.Y.Z`) and
   add an `[invidious]` section to `mopidy.conf`.
3. **Account integration:** `PlaylistsProvider` backed by
   `/api/v1/auth/playlists` (Invidious API token) to show, create, and edit
   your Invidious playlists, plus subscriptions as browsable channels.
4. **Nice to have:** "Radio" from `recommendedVideos`, channel playlists/
   releases tabs, search suggestions, continuation-based paging for long
   channels, CI (GitHub Actions: ruff + pytest), and PyPI release.
