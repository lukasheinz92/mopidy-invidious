"""Drive a running Mopidy over JSON-RPC: search -> add -> play -> seek."""

import json
import sys
import time
import urllib.request

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:6680/mopidy/rpc"


def rpc(method, **params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    req = urllib.request.Request(
        URL, body.encode(), {"Content-Type": "application/json"}
    )
    resp = json.load(urllib.request.urlopen(req, timeout=60))
    if "error" in resp:
        raise RuntimeError(f"{method}: {resp['error']}")
    return resp["result"]


def step(name, fn):
    t = time.monotonic()
    result = fn()
    print(f"[{time.monotonic() - t:5.2f}s] {name}")
    return result


root = step("browse root", lambda: rpc("core.library.browse", uri="invidious:root"))
print("   ", [r["name"] for r in root])
pls = step(
    "browse playlists",
    lambda: rpc("core.library.browse", uri="invidious:directory:playlists"),
)
print("   ", [r["name"] for r in pls])
chs = step(
    "browse channels",
    lambda: rpc("core.library.browse", uri="invidious:directory:channels"),
)
print("   ", [r["name"] for r in chs])

res = step(
    "search 'daft punk one more time'",
    lambda: rpc(
        "core.library.search",
        query={"any": ["daft punk one more time"]},
        uris=["invidious:"],
    ),
)
r = res[0]
counts = {k: len(r.get(k, [])) for k in ("tracks", "albums", "artists")}
print("   ", ", ".join(f"{n} {k}" for k, n in counts.items()))
print("    artists:", [a["name"] for a in r.get("artists", [])])
print("    albums: ", [a["name"] for a in r.get("albums", [])])
for t in r["tracks"][:3]:
    print(
        "   ",
        t["uri"],
        "|",
        ", ".join(a["name"] for a in t.get("artists", [])),
        "-",
        t["name"],
        t.get("length"),
    )

uri = r["tracks"][0]["uri"]
imgs = step("get_images", lambda: rpc("core.library.get_images", uris=[uri]))
print("   ", imgs[uri][0]["uri"])

pl_tracks = step(
    "lookup playlist",
    lambda: rpc("core.library.lookup", uris=["invidious:playlist:PLA95EFE7EDEF0514F"]),
)
print("    playlist tracks:", len(pl_tracks["invidious:playlist:PLA95EFE7EDEF0514F"]))

rpc("core.tracklist.clear")
step("tracklist.add", lambda: rpc("core.tracklist.add", uris=[uri]))
step("playback.play", lambda: rpc("core.playback.play"))

ok = False
for _ in range(30):
    time.sleep(1)
    state, pos = rpc("core.playback.get_state"), rpc("core.playback.get_time_position")
    if state == "playing" and pos > 2000:
        ok = True
        break
print(f"    state={state} position={pos}ms")

rpc("core.playback.seek", time_position=120_000)
time.sleep(4)
pos = rpc("core.playback.get_time_position")
print(f"    after seek to 120s: position={pos}ms")
rpc("core.playback.stop")

seek_ok = 120_000 <= pos < 130_000
print("RESULT:", "PASS" if ok and seek_ok else "FAIL")
sys.exit(0 if ok and seek_ok else 1)
