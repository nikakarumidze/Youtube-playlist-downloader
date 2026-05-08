#!/usr/bin/env python3
import subprocess
import sys
import re
import shutil
import json
import csv
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
PLAYLIST_URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"
OUTPUT_DIR   = "./downloads"
AUDIO_ONLY   = True   # True = audio only (.opus), False = full video (.mkv)
# ─────────────────────────────────────────────────────────────────────────────


def check_dependencies():
    missing = [t for t in ["yt-dlp", "ffmpeg"] if not shutil.which(t)]
    if missing:
        print(f"Missing: {', '.join(missing)}")
        print("  yt-dlp:  pip install yt-dlp")
        print("  ffmpeg:  https://www.gyan.dev/ffmpeg/builds/")
        sys.exit(1)


def build_cmd():
    base = [
        "yt-dlp",
        "--output",           f"{OUTPUT_DIR}/%(playlist_title)s/%(playlist_index)s_%(title)s.%(ext)s",
        "--embed-metadata",
        "--embed-thumbnail",
        "--write-info-json",
        "--continue",
        "--no-overwrites",
        "--retries",          "10",
        "--fragment-retries", "10",
        "--progress",
    ]
    if AUDIO_ONLY:
        base += [
            "--format",        "bestaudio",
            "--extract-audio",
            "--audio-format",  "opus",
            "--audio-quality", "0",
        ]
    else:
        base += [
            "--format",              "bestvideo+bestaudio/best",
            "--merge-output-format", "mkv",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",           "en",
        ]
    base.append(PLAYLIST_URL)
    return base



def download_playlist():
    print(f"\n── Step 1: Downloading ──")
    print(f"Playlist  : {PLAYLIST_URL}")
    print(f"Output    : {OUTPUT_DIR}")
    print(f"Mode      : {'Audio only (Opus)' if AUDIO_ONLY else 'Video (MKV)'}\n")

    result = subprocess.run(build_cmd())

    # Code 1 = partial failure (unavailable/private videos) — acceptable
    # Anything else (2 = usage error, etc.) = real problem
    if result.returncode not in (0, 1):
        print(f"yt-dlp failed with code {result.returncode}")
        sys.exit(result.returncode)

    print("\n── Download complete ──")

def get_playlist_title() -> str:
    folders = [f for f in Path(OUTPUT_DIR).iterdir() if f.is_dir()]
    if folders:
        return max(folders, key=lambda f: f.stat().st_ctime).name
    return ""

def organize():
    print(f"\n── Step 2: Organizing ──")
    extensions = ["opus", "mkv", "mp4", "webm", "m4a"]
    records    = []

    json_files = sorted(Path(OUTPUT_DIR).glob("*/*.info.json"))
    if not json_files:
        print("No .info.json files found — nothing to organize.")
        return

    for json_file in json_files:
        if json_file.stem.startswith("00_"):
            continue

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                info = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [warn] Could not read {json_file.name}: {e}")
            continue

        media_file = None
        stem = json_file.with_suffix("").with_suffix("")
        for ext in extensions:
            candidate = stem.with_suffix(f".{ext}")
            if candidate.exists():
                media_file = candidate
                break

        if not media_file:
            print(f"  [warn] No media file found for: {json_file.name}")
            continue

        # Build new filename from metadata
        title = info.get("title") or stem.name
        # Try these fields in order for the artist name
        artist = (
            info.get("artist")
            or info.get("creator")
            or info.get("uploader")
            or info.get("channel")
            or "Unknown"
        )
        # artist can be "Artist1, Artist2" — take only the first
        artist = artist.split(",")[0].strip()

        # Sanitize for Windows filesystem
        def sanitize(s: str) -> str:
            return re.sub(r'[\\/*?:"<>|]', "", s).strip()

        new_name  = f"{sanitize(artist)} - {sanitize(title)}{media_file.suffix}"

        tags     = info.get("tags") or []
        
        dest_dir = media_file.parent 

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / new_name

        if dest_file.exists():
            print(f"  [skip] Already organized: {new_name}")
        else:
            shutil.move(str(media_file), str(dest_file))\

        records.append({
            "filename":      dest_file.name,
            "title":         title,
            "artist":        artist,
            "channel":       info.get("channel", info.get("uploader", "")),
            "duration_sec":  info.get("duration", ""),
            "upload_date":   info.get("upload_date", ""),
            "url":           info.get("webpage_url", ""),
            "downloaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    if records:
        csv_path    = Path(OUTPUT_DIR) / "playlist_log.csv"
        file_exists = csv_path.exists()
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerows(records)
        print(f"\n  Organized {len(records)} files")
        print(f"  Log → {csv_path}")
def cleanup():
    print(f"\n── Step 3: Cleanup ──")
    deleted = []

    # Scan all levels inside OUTPUT_DIR
    for pattern in ["**/*.info.json", "**/*.temp", "**/*.ytdl", "**/*.part"]:
        for f in Path(OUTPUT_DIR).glob(pattern):
            try:
                f.unlink()
                deleted.append(f.name)
                print(f"  [deleted]  {f.name}")
            except OSError as e:
                print(f"  [warn] Could not delete {f.name}: {e}")

    if not deleted:
        print("  Nothing to clean up.")
    else:
        print(f"\n  Deleted {len(deleted)} leftover files")


if __name__ == "__main__":
    check_dependencies()
    download_playlist()
    title = get_playlist_title()
    organize()
    cleanup()