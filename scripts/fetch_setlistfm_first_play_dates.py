#!/usr/bin/env python3
"""
Fetch earliest known play dates for Bruce Springsteen songs using the setlist.fm API
and merge with the studio songs list.

Inputs:
- data/springsteen_songs_simple_unique.csv (columns: song_title, album_release_date_iso)

Outputs:
- data/springsteen_songs_with_first_play.csv (columns: song_title, album_release_date_iso, first_play_date)

Environment:
- SETLISTFM_API_KEY must be set to your setlist.fm API key.

Notes:
- We page through all Springsteen setlists once and compute earliest play date per normalized song title.
- We normalize titles case-insensitively and by stripping punctuation/extra whitespace. You can tweak normalization as needed.
"""
import csv
import os
import re
import time
import json
import math
import unicodedata
from datetime import datetime
from typing import Dict, List, Optional

import requests

ARTIST_MBID = "70248960-cb53-4ea4-943a-edb18f7d336f"  # Bruce Springsteen
BASE_URL = "https://api.setlist.fm/rest/1.0"
UA = "songs-setlistfm/0.1 (contact: none)"
SLEEP_SEC = 1.1  # polite default; increase if you see 429s
CACHE_DIR = "data/cache/setlistfm"
INPUT_UNIQUE = "data/springsteen_songs_simple_unique.csv"
OUTPUT_MERGED = "data/springsteen_songs_with_first_play.csv"


def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def norm_title(s: str) -> str:
    if not s:
        return ""
    # Unicode NFKD, remove diacritics
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().strip()
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    # Remove most punctuation (keep numbers and letters)
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    return s


def parse_event_date(d: str) -> Optional[str]:
    """setlist.fm uses dd-MM-yyyy; return ISO yyyy-MM-dd."""
    if not d:
        return None
    try:
        dt = datetime.strptime(d, "%d-%m-%Y")
        return dt.date().isoformat()
    except Exception:
        return None


def api_get(path: str, params: Dict = None, api_key: str = "") -> requests.Response:
    url = f"{BASE_URL}{path}"
    headers = {
        "Accept": "application/json",
        "x-api-key": api_key,
        "User-Agent": UA,
        "Accept-Language": "en",
    }
    resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
    if resp.status_code == 429:
        # basic backoff
        time.sleep(3.0)
        resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp


def fetch_all_setlists_for_artist(api_key: str) -> List[Dict]:
    ensure_cache_dir()
    all_setlists: List[Dict] = []

    # Try to discover total pages via initial request
    page = 1
    params = {"p": page}
    cache_path = os.path.join(CACHE_DIR, f"artist_{ARTIST_MBID}_page_{page}.json")

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        resp = api_get(f"/artist/{ARTIST_MBID}/setlists", params=params, api_key=api_key)
        payload = resp.json()
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        time.sleep(SLEEP_SEC)

    total = payload.get("total")
    per_page = len(payload.get("setlist", [])) or 20  # default to 20 if unknown
    total_pages = payload.get("page", 1)
    # Guess total pages if not provided: ceil(total/per_page)
    if isinstance(total, int) and per_page:
        total_pages = math.ceil(total / per_page)

    all_setlists.extend(payload.get("setlist", []))

    # Fetch remaining pages
    for page in range(2, total_pages + 1):
        params = {"p": page}
        cache_path = os.path.join(CACHE_DIR, f"artist_{ARTIST_MBID}_page_{page}.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            resp = api_get(f"/artist/{ARTIST_MBID}/setlists", params=params, api_key=api_key)
            payload = resp.json()
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            time.sleep(SLEEP_SEC)
        all_setlists.extend(payload.get("setlist", []))

    return all_setlists


essential_keys = ("sets", "set")

def build_earliest_play_map(setlists: List[Dict]) -> Dict[str, str]:
    earliest: Dict[str, str] = {}
    for sl in setlists:
        event_iso = parse_event_date(sl.get("eventDate"))
        if not event_iso:
            continue
        sets = sl.get("sets") or {}
        for s in sets.get("set", []) or []:
            for song in s.get("song", []) or []:
                name = song.get("name")
                if not name:
                    continue
                key = norm_title(name)
                if not key:
                    continue
                prev = earliest.get(key)
                if prev is None or event_iso < prev:
                    earliest[key] = event_iso
    return earliest


def load_unique_songs(path: str) -> List[Dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def merge_and_write(songs: List[Dict], earliest_map: Dict[str, str], out_path: str) -> int:
    out_rows: List[Dict] = []
    for r in songs:
        title = r.get("song_title") or ""
        date_iso = r.get("album_release_date_iso") or ""
        key = norm_title(title)
        first_play = earliest_map.get(key, "")
        out_rows.append({
            "song_title": title,
            "album_release_date_iso": date_iso,
            "first_play_date": first_play,
        })
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["song_title", "album_release_date_iso", "first_play_date"])
        w.writeheader()
        w.writerows(out_rows)
    return len(out_rows)


def main():
    api_key = os.environ.get("SETLISTFM_API_KEY", "").strip()
    if not api_key:
        print("ERROR: SETLISTFM_API_KEY not set. Export your setlist.fm API key in the environment and re-run.")
        print("Example: export SETLISTFM_API_KEY=your_key_here")
        return 2

    songs = load_unique_songs(INPUT_UNIQUE)
    print(f"Loaded {len(songs)} unique songs from {INPUT_UNIQUE}")
    print("Fetching all setlists for Bruce Springsteen (cached)… this may take a while on first run…")
    setlists = fetch_all_setlists_for_artist(api_key)
    print(f"Fetched {len(setlists)} setlists")

    print("Building earliest play map…")
    earliest_map = build_earliest_play_map(setlists)
    print(f"Found earliest dates for {len(earliest_map)} distinct song titles in setlists")

    print("Merging and writing output…")
    count = merge_and_write(songs, earliest_map, OUTPUT_MERGED)
    print(f"Wrote {count} rows to {OUTPUT_MERGED}")


if __name__ == "__main__":
    raise SystemExit(main())
