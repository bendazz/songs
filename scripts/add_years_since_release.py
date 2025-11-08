#!/usr/bin/env python3
"""
Add years_since_release and catalog_size_at_release to an existing all-plays CSV
without re-fetching setlists.

Inputs:
- data/springsteen_songs_all_plays.csv (song_title, album_release_date_iso, play_date_iso)
- data/springsteen_songs_simple_unique.csv (song_title, album_release_date_iso)

Output:
- data/springsteen_songs_all_plays_with_years.csv (adds years_since_release, catalog_size_at_release)
"""
import csv
from datetime import date
from typing import Optional, Dict, List, Tuple

IN_PATH = "data/springsteen_songs_all_plays.csv"
OUT_PATH = "data/springsteen_songs_all_plays_with_years.csv"
SONGS_PATH = "data/springsteen_songs_simple_unique.csv"


def parse_iso(d: str) -> Optional[date]:
    if not d:
        return None
    try:
        return date.fromisoformat(d)
    except Exception:
        return None


def years_between(release_iso: str, play_iso: str) -> str:
    r = parse_iso(release_iso)
    p = parse_iso(play_iso)
    if not r or not p:
        return ""
    days = (p - r).days
    years = days / 365.2425
    return f"{years:.2f}"


def load_songs(path: str) -> List[Tuple[str, date]]:
    rows: List[Tuple[str, date]] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            title = row.get("song_title") or ""
            iso = row.get("album_release_date_iso") or ""
            d = parse_iso(iso)
            if title and d:
                rows.append((title, d))
    return rows


def build_catalog_size_by_song(path: str) -> Dict[str, int]:
    # Compute cumulative catalog size per unique release date
    songs = load_songs(path)
    # count songs on each date
    from collections import Counter
    by_date = Counter([d for _, d in songs])
    cumulative: Dict[date, int] = {}
    running = 0
    for d in sorted(by_date.keys()):
        running += by_date[d]
        cumulative[d] = running
    # map each song to cumulative count at its release date
    mapping: Dict[str, int] = {}
    for title, d in songs:
        mapping[title] = cumulative[d]
    return mapping


def main():
    with open(IN_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Build catalog size mapping
    catalog_size_by_song = build_catalog_size_by_song(SONGS_PATH)

    for r in rows:
        r["years_since_release"] = years_between(r.get("album_release_date_iso", ""), r.get("play_date_iso", ""))
        r["catalog_size_at_release"] = str(catalog_size_by_song.get(r.get("song_title", ""), ""))

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys()) if rows else [
            "song_title",
            "album_release_date_iso",
            "play_date_iso",
            "years_since_release",
            "catalog_size_at_release",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
