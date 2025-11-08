#!/usr/bin/env python3
"""
Add years_since_release to an existing all-plays CSV without re-fetching setlists.

Input:  data/springsteen_songs_all_plays.csv (song_title, album_release_date_iso, play_date_iso)
Output: data/springsteen_songs_all_plays_with_years.csv (adds years_since_release)
"""
import csv
from datetime import date
from typing import Optional

IN_PATH = "data/springsteen_songs_all_plays.csv"
OUT_PATH = "data/springsteen_songs_all_plays_with_years.csv"


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


def main():
    with open(IN_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        r["years_since_release"] = years_between(r.get("album_release_date_iso", ""), r.get("play_date_iso", ""))

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys()) if rows else [
            "song_title", "album_release_date_iso", "play_date_iso", "years_since_release"
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
