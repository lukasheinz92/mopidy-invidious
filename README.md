# Mopidy-Invidious

A [Mopidy](https://mopidy.com/) 4 extension for searching, browsing and playing
music from a self-hosted [Invidious](https://invidious.io/) instance.

Its content shows up in any Mopidy client under Browse → Invidious and in search results.

> **Note:** This is a personal hobby project, built for a self-hosted home setup
> and intended for private, non-commercial use. It is provided as is, without
> warranty or support. It does not download or redistribute any content; it only
> talks to an Invidious instance you run yourself. You are responsible for
> complying with the terms of service of the services you use and with the laws
> of your country. This project is not affiliated with YouTube, Google or Invidious.

## Features

- **Search**: videos (as tracks), playlists (as albums) and channels (as artists)
- **Browse**: a curated list of playlists and channels (`playlists`, `channels`)
- **Playback**: audio is streamed through Invidious (`local=true`), so Mopidy never
  talks to YouTube directly, and stream URLs never expire
- **Lightweight**: no dependencies beyond Mopidy 4 itself

## Requirements

- Mopidy >= 4.0, Python >= 3.13
- An Invidious instance reachable from Mopidy (with invidious-companion)
- GStreamer plugins for Opus/WebM and AAC/MP4 (`gstreamer1.0-plugins-good`,
  `-bad`)

## Installation

```sh
pip install mopidy-invidious
# or the latest development version from GitHub
pip install git+https://github.com/lukasheinz92/mopidy-invidious
# or from a local checkout
pip install /path/to/mopidy-invidious
```

## Configuration

```ini
[invidious]
enabled = true
# Invidious as seen from Mopidy (API + audio)
base_url = http://invidious-app:3000
# Invidious as seen from Mopidy clients (cover art); defaults to base_url
public_url = https://invidious.example.org
timeout = 15
# Max songs (videos) per search; `search_results` is a deprecated alias
search_track_results = 20
# Max playlists (as albums) / channels (as artists) above the tracks; only
# official/album playlists and channels named like the query. 0 disables.
search_playlist_results = 5
search_channel_results = 3
# Preferred audio formats, first available wins:
# 251 = Opus ~160k, 140 = AAC 128k, 250 = Opus ~70k, 249 = Opus ~50k
audio_itags = 251, 140, 250, 249
# Split "Artist - Title" video titles into artist and track name
parse_titles = true
# Shown under Browse > Invidious
playlists = PLxxxxxxxxxxxxxxxx, PLyyyyyyyyyyyyyyyy
channels = UCxxxxxxxxxxxxxxxxxxxxxx
cache_ttl = 3600
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design.

## Development

Unit tests and an end-to-end test run on the Docker host, inside the same
image as production Mopidy, without touching the running instance:

```sh
dev/remote.sh test   # pytest in a throwaway mopidy:latest container
dev/remote.sh e2e    # isolated Mopidy + extension: search, play, seek
dev/remote.sh logs
dev/remote.sh down
```

Override `HOST`, `IMAGE` or `NETWORK` via environment variables.

## License

Apache-2.0
