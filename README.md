# 🎵 YouTube Playlist Downloader & Organizer

Downloads YouTube playlists at highest quality and automatically organizes music into genre/BPM subfolders.

---

## Features

- Downloads full YouTube playlists (audio or video)
- Highest quality audio — native Opus (no re-encoding)
- Organizes files by **genre** and **BPM range** (BPM ranges only for applicable genres)
- Renames files to `Artist - Title` format
- Cleans up title noise: removes `(Lyrics)`, `[Official Video]`, `(Audio)`, etc.
- Embeds all detected genre tags into file metadata properties
- Logs all downloads to `playlist_log.csv`
- Cleans up leftover temp/metadata files after download
- Separate standalone organizer for existing music folders using **Last.fm API** + local BPM detection

---

## Requirements

- Python 3.11+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://www.gyan.dev/ffmpeg/builds/)
- [librosa](https://librosa.org/)
- [requests](https://pypi.org/project/requests/)
- [mutagen](https://mutagen.readthedocs.io/)

```bash
pip install yt-dlp librosa requests mutagen
```

ffmpeg must be installed separately and available in PATH.

---

## Files

| File | Purpose |
|---|---|
| `run.py` | Main entry point — orchestrates download and/or organize steps |
| `converter.py` | Downloader + organizer (called by run.py) |
| `organizer.py` | Standalone organizer for existing folders (called by run.py) |

---

## run.py

The main entry point. Controls which steps run and passes config between them.

### Config

```python
DOWNLOAD      = True   # Run the download step (converter.py)
TRANSFORM     = True   # Run the organize step (organizer.py)
PLAYLIST_LINK = "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"

FOLDER_NAME   = "/my-folder"  # Used by TRANSFORM if DOWNLOAD is False
```

### Usage

```bash
py run.py
```

### How folder naming works

- If `DOWNLOAD = True`, the output folder name is auto-detected from the most recently created folder inside `downloads/` after the download completes, and passed into the transform step automatically.
- If `DOWNLOAD = False`, `FOLDER_NAME` is used instead.
- If the detected folder name is blank for any reason, it falls back to `FOLDER_NAME`.

### Pipeline

```
run.py
├── (if DOWNLOAD) → converter.py  →  downloads/Playlist Name/
│                                      detects newest folder → "Playlist Name"
└── (if TRANSFORM) → organizer.py "Playlist Name"  →  organized/Playlist Name/
```

---

## converter.py

Downloads a YouTube playlist and organizes it automatically.

### Config

```python
PLAYLIST_URL = "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"
OUTPUT_DIR   = "./downloads"
AUDIO_ONLY   = True   # True = .opus audio, False = .mkv video
```

### Usage

Can be run standalone:
```bash
py converter.py "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"
```

Or called via `run.py` (recommended).

### Pipeline

1. **Download** — yt-dlp fetches all available videos, skips unavailable/private/copyright-claimed ones (exit code 1 is treated as non-fatal)
2. **Organize** — reads `.info.json` metadata, detects genre from YouTube tags, detects BPM via librosa, renames to `Artist - Title`, moves into subfolders
3. **Cleanup** — deletes all `.info.json`, `.temp`, `.part` leftovers
4. **Returns** the name of the newly created playlist folder (newest folder by creation time)

### Output Structure

```
downloads/
└── Playlist Name/
    ├── house/
    │   ├── 120-135bpm/
    │   │   └── Artist - Title.opus
    │   └── 135-150bpm/
    │       └── Artist - Title.opus
    ├── hip-hop/
    │   └── Artist - Title.opus
    ├── uncategorized/
    │   └── unknown-bpm/
    │       └── Artist - Title.opus
    └── playlist_log.csv
```

---

## organizer.py

Organizes an existing folder of audio files. Uses **Last.fm** for genre detection and **librosa** for BPM.

### Config

```python
LASTFM_API_KEY = "your_lastfm_api_key"  # from .env
```

Get a free key at [last.fm/api/account/create](https://www.last.fm/api/account/create) — no approval needed, instant.

### Usage

Can be run standalone:
```bash
py organizer.py "/folder-name"
```

This reads from `./downloads/folder-name` and writes to `./organized/folder-name`. Original files are **copied**, not moved.

Or called via `run.py` (recommended) — folder name is passed in automatically after a download.

### Output Structure

```
organized/
└── Playlist Name/
    ├── house/
    │   ├── 120-135bpm/
    │   │   └── Artist - Title.opus
    │   └── 135-150bpm/
    │       └── Artist - Title.opus
    ├── hip-hop/
    │   └── Artist - Title.opus
    ├── soul/
    │   └── Artist - Title.opus
    └── uncategorized/
        └── unknown-bpm/
            └── Artist - Title.opus
```

---

## Genre Detection

### How it works

Last.fm returns crowd-sourced tags sorted by weight. Tags are matched against `GENRE_MAP` keywords. Instead of first-match, every genre is **scored** by number of matching tags — the genre with the most matches wins.

```python
GENRE_MAP = {
    "house":      ["house", "deep house", "tech house", "disco house", "afro house"],
    "disco":      ["disco", "nu-disco", "italo disco", "boogie"],
    "soul":       ["soul", "neo soul", "rhythm and blues"],
    "jazz":       ["jazz", "jazz funk", "acid jazz", "nu jazz"],
    "funk":       ["funk", "funk soul", "p-funk"],
    "electronic": ["electronic", "electronica", "synth", "ambient", "downtempo"],
    "dance":      ["dance", "edm", "club"],
    "pop":        ["pop", "indie pop", "dream pop"],
    "hip-hop":    ["hip hop", "hip-hop", "rap", "lo-fi", "lofi", "rnb", "r&b"],
    "classical":  ["classical", "orchestral", "piano"],
    "rock":       ["rock", "indie rock", "alternative"],
    "reggae":     ["reggae", "dub", "dancehall"],
}
```

Add or edit keywords freely — more specific keywords reduce mismatches.

### Fallback chain

1. `track.getTopTags` — track-level tags (most specific)
2. `artist.getTopTags` — artist-level tags if track has none
3. `track.search` — resolves artist name if not parseable from filename
4. `uncategorized` — if nothing matches

---

## BPM Detection

BPM is detected locally from the audio using librosa (analyzes first 60 seconds). Only applied to these genres:

```python
BPM_GENRES = {"house", "disco", "dance", "electronic", "uncategorized"}
```

Files are grouped into 15 BPM buckets:

| Folder | BPM Range |
|---|---|
| `105-120bpm` | 105 – 120 |
| `120-135bpm` | 120 – 135 |
| `135-150bpm` | 135 – 150 |

Other genres (hip-hop, soul, rock, etc.) go directly into the genre folder without BPM subfolders.

---

## File Naming

Files are renamed to `Artist - Title.ext`. Title is cleaned of common YouTube noise:

| Removed pattern | Example |
|---|---|
| `(Lyrics)` / `[Lyrics]` / `- Lyrics` | `Song Title (Lyrics)` → `Song Title` |
| `(Official Video)` / `[Official Video]` | `Song Title (Official Video)` → `Song Title` |
| `(Audio)` / `(Official Audio)` | `Song Title (Audio)` → `Song Title` |
| `(Official Music Video)` | `Song Title (Official Music Video)` → `Song Title` |

If the artist cannot be parsed from the filename, Last.fm search is used to resolve it.

---

## Genre Embedding

All detected Last.fm tags are embedded into the file's metadata `genre` field as a comma-separated string, visible in Windows file properties and media players.

Supported formats: `.opus`, `.mp3`, `.m4a`, `.mp4`, `.flac`

---

## Known Limitations

- Unavailable, private, members-only, or copyright-claimed videos are skipped (yt-dlp exits with code 1 — handled as non-fatal)
- Genre detection quality depends on Last.fm tag coverage — obscure tracks may fall back to `uncategorized`
- BPM detection is an estimate (±2-3 BPM typical) — can halve/double for tracks with irregular beats
- Filenames without `Artist - Title` format will attempt artist resolution via Last.fm search

---

## Notes on Audio Quality

| Format | Why |
|---|---|
| Opus | YouTube's native audio format (~128-160kbps). Kept as-is — no re-encoding, no quality loss |
| MP3 320 | Avoided — transcoding Opus→MP3 is lossy-to-lossy, degrades quality |
| MKV | Used for video mode — universal container, accepts any codec without re-encoding |