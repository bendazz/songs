#!/usr/bin/env python3
"""
Produce a CSV with every instance Bruce Springsteen played any song from the
studio-unique list, using the setlist.fm API.

Inputs:
- data/springsteen_songs_simple_unique.csv (columns: song_title, album_release_date_iso)

Output:
- data/springsteen_songs_all_plays.csv (columns: song_title, album_release_date_iso, play_date_iso)

Env:
- SETLISTFM_API_KEY must be set to your setlist.fm API key.

Notes:
- We fetch all setlists for Springsteen with caching and polite delays.
- We normalize titles (casefold, strip punctuation/diacritics) to match between studio titles and setlist songs.
- We include every occurrence; if a song appears twice in one show, both are recorded (rare).
"""
import csv
import json
import math
import os
import re
import time
import unicodedata
from datetime import datetime, date
from typing import Dict, Iterable, List, Optional

import requests

ARTIST_MBID = "70248960-cb53-4ea4-943a-edb18f7d336f"  # Bruce Springsteen
BASE_URL = "https://api.setlist.fm/rest/1.0"
UA = "songs-setlistfm/0.1 (contact: none)"
SLEEP_SEC = 1.1
CACHE_DIR = "data/cache/setlistfm"
INPUT_UNIQUE = "data/springsteen_songs_simple_unique.csv"
OUTPUT_ALL_PLAYS = "data/springsteen_songs_all_plays.csv"


def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def norm_title(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    return s


def parse_event_date(d: str) -> Optional[str]:
    # setlist.fm: dd-MM-yyyy
    if not d:
        return None
    try:
        return datetime.strptime(d, "%d-%m-%Y").date().isoformat()
    except Exception:
        return None


def parse_iso_date(d: str) -> Optional[date]:
    if not d:
        return None
    try:
        return date.fromisoformat(d)
    except Exception:
        return None


def years_between(release_iso: str, play_iso: str) -> str:
    """Return years difference as a string with 2 decimal precision; empty if missing."""
    rd = parse_iso_date(release_iso)
    pd = parse_iso_date(play_iso)
    if not rd or not pd:
        return ""
    days = (pd - rd).days
    years = days / 365.2425  # average tropical year
    return f"{years:.2f}"


def api_get(path: str, params: Dict, api_key: str) -> Dict:
    url = f"{BASE_URL}{path}"
    headers = {
        "Accept": "application/json",
        "x-api-key": api_key,
        "User-Agent": UA,
        "Accept-Language": "en",
    }
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code == 429:
        # Backoff and retry once
        time.sleep(3.0)
        resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def iter_all_setlists(api_key: str) -> Iterable[Dict]:
    ensure_cache_dir()
    # initial page to determine total pages
    page = 1
    cache_path = os.path.join(CACHE_DIR, f"artist_{ARTIST_MBID}_page_{page}.json")
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        payload = api_get(f"/artist/{ARTIST_MBID}/setlists", {"p": page}, api_key)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        time.sleep(SLEEP_SEC)

    total = payload.get("total")
    per_page = len(payload.get("setlist", [])) or 20
    total_pages = payload.get("page", 1)
    if isinstance(total, int) and per_page:
        total_pages = math.ceil(total / per_page)

    # yield first page
    for sl in payload.get("setlist", []) or []:
        yield sl

    # subsequent pages
    for page in range(2, total_pages + 1):
        cache_path = os.path.join(CACHE_DIR, f"artist_{ARTIST_MBID}_page_{page}.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            payload = api_get(f"/artist/{ARTIST_MBID}/setlists", {"p": page}, api_key)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            time.sleep(SLEEP_SEC)
        for sl in payload.get("setlist", []) or []:
            yield sl


def load_unique_songs(path: str) -> Dict[str, Dict[str, str]]:
    # returns normalized title -> row
    with open(path, newline="", encoding="utf-8") as f:
        data = list(csv.DictReader(f))
    mapping: Dict[str, Dict[str, str]] = {}
    for row in data:
        title = row.get("song_title") or ""
        if not title:
            continue
        mapping[norm_title(title)] = {
            "song_title": title,
            "album_release_date_iso": row.get("album_release_date_iso") or "",
        }
    return mapping


def main() -> int:
    api_key = os.environ.get("SETLISTFM_API_KEY", "").strip()
    if not api_key:
        print("ERROR: SETLISTFM_API_KEY not set. Export your setlist.fm API key and re-run.")
        print("Example: export SETLISTFM_API_KEY=your_key_here")
        return 2

    studio_map = load_unique_songs(INPUT_UNIQUE)
    print(f"Loaded {len(studio_map)} studio-unique songs from {INPUT_UNIQUE}")

    out_rows: List[Dict[str, str]] = []
    count_setlists = 0
    for sl in iter_all_setlists(api_key):
        count_setlists += 1
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
                studio_row = studio_map.get(key)
                if not studio_row:
                    # Not a studio song under our definition; skip
                    continue
                out_rows.append({
                    "song_title": studio_row["song_title"],
                    "album_release_date_iso": studio_row["album_release_date_iso"],
                    "play_date_iso": event_iso,
                    "years_since_release": years_between(studio_row["album_release_date_iso"], event_iso),
                })

    os.makedirs(os.path.dirname(OUTPUT_ALL_PLAYS), exist_ok=True)
    with open(OUTPUT_ALL_PLAYS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["song_title", "album_release_date_iso", "play_date_iso", "years_since_release"])
        w.writeheader()
        w.writerows(out_rows)

    print(f"Processed {count_setlists} setlists; wrote {len(out_rows)} rows to {OUTPUT_ALL_PLAYS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
