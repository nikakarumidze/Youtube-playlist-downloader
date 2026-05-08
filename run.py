#!/usr/bin/env python3
import subprocess
import sys

# ── Config ────────────────────────────────────────────────────────────────────
DOWNLOAD      = True
TRANSFORM     = True
PLAYLIST_LINK = "https://www.youtube.com/YOUR_PLAYLIST"

FOLDER_NAME = "/FOLDER_NAME"
# ─────────────────────────────────────────────────────────────────────────────


def run_download() -> str:
    print("══════════════════════════════════════")
    print("  Step 1: Download & Organize Playlist")
    print("══════════════════════════════════════")
    cmd = [sys.executable, "converter.py"]
    if PLAYLIST_LINK:
        cmd.append(PLAYLIST_LINK)
    result = subprocess.run(cmd, capture_output=False, text=True)  # keep normal terminal output
    
    # Re-run just to grab the title (already cached by yt-dlp, very fast)
    title_result = subprocess.run(
        [sys.executable, "-c",
         f"import converter; print(converter.get_playlist_title())"],
        capture_output=True, text=True
    )
    playlist_title = title_result.stdout.strip()

    if result.returncode not in (0, 1):
        print(f"converter.py failed with code {result.returncode}")
        sys.exit(result.returncode)

    return playlist_title


def run_transform(folder_name: str = FOLDER_NAME):
    print("══════════════════════════════════════")
    print("  Step 2: Transform Existing Folder")
    print("══════════════════════════════════════")
    result = subprocess.run([sys.executable, "organizer.py", folder_name])
    if result.returncode != 0:
        print(f"organizer.py failed with code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    if not DOWNLOAD and not TRANSFORM:
        print("Nothing to do — both DOWNLOAD and TRANSFORM are False.")
        sys.exit(0)

    if DOWNLOAD:
        playlist_title = run_download()
        print(f"Playlist: {playlist_title}")

    if TRANSFORM:
        if not DOWNLOAD:
            playlist_title = FOLDER_NAME
        run_transform(playlist_title)

    print("\n══ All done ══")