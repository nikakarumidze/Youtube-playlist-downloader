#!/usr/bin/env python3
"""
Organizes all audio files in a folder into genre subfolders using Spotify API.
Usage: py organize.py "path/to/folder" "path/to/output_folder"
"""

import sys
import os
import re
import shutil
import requests
import librosa
from pathlib import Path
from dotenv import find_dotenv, load_dotenv

# Load dotenv files
dotenv_path =find_dotenv()
load_dotenv(dotenv_path)

# ── Config ────────────────────────────────────────────────────────────────────
LASTFM_API_KEY = os.getenv('API_KEY')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
AUDIO_EXTENSIONS      = {".opus", ".mp3", ".m4a", ".flac", ".wav", ".mkv", ".mp4"}
# ─────────────────────────────────────────────────────────────────────────────
BPM_GENRES = {"house", "disco", "dance", "electronic", "uncategorized"}


GENRE_MAP = {
    "house":      ["house", "deep house", "tech house", "disco house", "afro house", "chicago house"],
    "disco":      ["disco", "nu-disco", "italo disco", "boogie"],
    "soul":       ["soul", "neo soul", "r&b", "rnb", "rhythm and blues"],
    "jazz":       ["jazz", "jazz funk", "acid jazz", "nu jazz", "bebop"],
    "funk":       ["funk", "funk soul", "p-funk"],
    "electronic": ["electronic", "electronica", "synth", "ambient", "downtempo", "idm"],
    "dance":      ["dance", "edm", "club", "dance pop"],
    "pop":        ["pop", "indie pop", "dream pop", "synthpop"],
    "hip-hop":    ["hip hop", "hip-hop", "rap", "lo-fi", "lofi", "trap"],
    "classical":  ["classical", "orchestral", "piano", "chamber"],
    "rock":       ["rock", "indie rock", "alternative", "post-rock"],
    "reggae":     ["reggae", "dub", "dancehall"],
}



def parse_filename(filepath: Path) -> tuple[str, str]:
    stem = filepath.stem
    stem = re.sub(r"^\d+_", "", stem).strip()
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return artist.strip(), title.strip()
    return "", stem.strip()

from mutagen.oggopus import OggOpus
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.id3 import ID3, TIT2, TPE1, TCON


def sanitize(s: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", s).strip()


def embed_genres(filepath: Path, genres: list[str]):
    genre_str = ", ".join(genres)
    try:
        if filepath.suffix == ".opus":
            audio = OggOpus(str(filepath))
            audio["genre"] = genre_str
            audio.save()
        elif filepath.suffix in (".m4a", ".mp4"):
            audio = MP4(str(filepath))
            audio["\xa9gen"] = genre_str
            audio.save()
        elif filepath.suffix == ".flac":
            audio = FLAC(str(filepath))
            audio["genre"] = genre_str
            audio.save()
        elif filepath.suffix == ".mp3":
            audio = ID3(str(filepath))
            audio.add(TCON(encoding=3, text=genre_str))
            audio.save()
    except Exception as e:
        print(f"    [warn] Could not embed genres: {e}")


def search_lastfm(artist: str, title: str) -> tuple[list[str], str]:
    junk = {"seen live", "favorites", "favourite", "love", "awesome", "cool", "beautiful", "amazing"}

    if not artist:
        search_resp = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method":  "track.search",
                "track":   title,
                "api_key": LASTFM_API_KEY,
                "format":  "json",
                "limit":   1,
            },
        )
        search_resp.raise_for_status()
        matches = search_resp.json().get("results", {}).get("trackmatches", {}).get("track", [])
        if matches:
            artist = matches[0].get("artist", "")
            print(f"    Found   : artist={artist}")

    if not artist:
        print(f"    [warn] Could not resolve artist")
        return [], ""

    resp = requests.get(
        "https://ws.audioscrobbler.com/2.0/",
        params={
            "method":  "track.getTopTags",
            "artist":  artist,
            "track":   title,
            "api_key": LASTFM_API_KEY,
            "format":  "json",
            "limit":   10,
        },
    )
    resp.raise_for_status()
    data = resp.json()

    tags = []
    if "error" not in data:
        tags = data.get("toptags", {}).get("tag", [])

    if not tags:
        resp2 = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method":  "artist.getTopTags",
                "artist":  artist,
                "api_key": LASTFM_API_KEY,
                "format":  "json",
                "limit":   10,
            },
        )
        resp2.raise_for_status()
        tags = resp2.json().get("toptags", {}).get("tag", [])

    if not tags:
        print(f"    [warn] No Last.fm tags found")
        return [], artist

    genres = [
        t["name"].lower() for t in tags
        if t["name"].lower() not in junk and int(t.get("count", 0)) > 0
    ]

    print(f"    Tags    : {genres[:5]}")
    return genres, artist

def detect_genre(genres: list[str]) -> str:
    genres_lower = [g.lower() for g in genres]
    scores = {}

    for genre, keywords in GENRE_MAP.items():
        score = 0
        for keyword in keywords:
            for tag in genres_lower:
                if keyword in tag:
                    score += 1
        if score > 0:
            scores[genre] = score

    if not scores:
        return genres[0].lower() if genres else "uncategorized"

    # Pick genre with most keyword matches
    best = max(scores, key=lambda g: scores[g])
    print(f"    Scores  : {dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))}")
    return best

def detect_bpm(filepath: Path) -> float | None:
    try:
        y, sr = librosa.load(str(filepath), sr=None, mono=True, duration=60)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo[0]) if hasattr(tempo, '__len__') else float(tempo)
        return round(bpm, 1)
    except Exception as e:
        print(f"    [warn] BPM detection failed: {e}")
        return None
    
def clean_title(title: str) -> str:
    # Remove lyrics suffixes in various forms
    patterns = [
        r'\s*\(lyrics\)',
        r'\s*\[lyrics\]',
        r'\s*-\s*lyrics',
        r'\s*lyrics',
        r'\s*\(official video\)',
        r'\s*\[official video\]',
        r'\s*-\s*official video',
        r'\s*\(audio\)',
        r'\s*\[audio\]',
        r'\s*-\s*audio',
        r'\s*\(official audio\)',
        r'\s*\[official audio\]',
        r'\s*-\s*official audio',
        r'\s*\(official music video\)',
        r'\s*\[official music video\]',
    ]
    for pattern in patterns:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE)
    return title.strip()


def bpm_subfolder(bpm: float) -> str:
    # Groups into 15 BPM buckets: 90-105, 105-120, 120-135, 135-150 ...
    low  = int(bpm // 15) * 15
    high = low + 15
    return f"{low}-{high}bpm"


def organize_folder(input_folder: str, output_folder: str):
    input_path  = Path(input_folder)
    output_path = Path(output_folder)

    if not input_path.exists() or not input_path.is_dir():
        print(f"Input folder not found: {input_path}")
        sys.exit(1)

    # Collect audio files — recursive to catch files in subfolders
    audio_files = [
        f for f in sorted(input_path.rglob("*"))
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
    ]

    if not audio_files:
        print(f"No audio files found in: {input_path}")
        sys.exit(0)

    print(f"\nInput    : {input_path}")
    print(f"Output   : {output_path}")
    print(f"Files    : {len(audio_files)} audio files found\n")

    results = {"copied": [], "skipped": [], "failed": []}

    for i, filepath in enumerate(audio_files, 1):
        print(f"[{i}/{len(audio_files)}] {filepath.name}")

        artist, title = parse_filename(filepath)
        title = clean_title(title)
        print(f"    Artist  : {artist or '(unknown)'}")
        print(f"    Title   : {title}")

        try:
            genres, resolved_artist = search_lastfm(artist, title)
        except requests.RequestException as e:
            print(f"    [error] Last.fm request failed: {e}")
            results["failed"].append(filepath.name)
            continue

        # Use resolved artist for naming if parse gave us nothing
        final_artist = resolved_artist if resolved_artist else artist

        print(f"    Genres  : {genres or ['(none)']}")
        genre = detect_genre(genres)
        print(f"    Assigned: {genre}")

        new_name = f"{sanitize(final_artist)} - {sanitize(title)}{filepath.suffix}"

        if genre in BPM_GENRES:
            bpm = detect_bpm(filepath)
            if bpm:
                print(f"    BPM     : {bpm}")
                dest_dir = output_path / genre / bpm_subfolder(bpm)
            else:
                dest_dir = output_path / genre / "unknown-bpm"
        else:
            dest_dir = output_path / genre

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / new_name

        if dest_file.exists():
            print(f"    [skip] Already exists in output")
            results["skipped"].append(new_name)
        else:
            shutil.copy2(str(filepath), str(dest_file))
            embed_genres(dest_file, genres)
            print(f"    Copied → {dest_file}")
            results["copied"].append(new_name)
        print()

    print("── Summary ──")
    print(f"  Copied   : {len(results['copied'])}")
    print(f"  Skipped  : {len(results['skipped'])}")
    print(f"  Failed   : {len(results['failed'])}")
    if results["failed"]:
        for f in results["failed"]:
            print(f"    - {f}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: py organize.py <input_folder> <output_folder>")
        sys.exit(1)

    organize_folder(sys.argv[1], sys.argv[2])