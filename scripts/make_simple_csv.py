#!/usr/bin/env python3
import csv
from collections import defaultdict
from typing import Dict, Tuple

SOURCE = "data/springsteen_studio_songs.csv"
OUTPUT_ALL = "data/springsteen_songs_simple.csv"
OUTPUT_UNIQUE = "data/springsteen_songs_simple_unique.csv"


def load_rows(path: str):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def main():
    all_rows = list(load_rows(SOURCE))
    # Write straightforward projection (keep all rows including duplicates across albums if any)
    with open(OUTPUT_ALL, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["song_title", "album_release_date_iso"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in all_rows:
            w.writerow({
                "song_title": r.get("song_title"),
                "album_release_date_iso": r.get("album_release_date_iso"),
            })

    # Deduplicate by song_title keeping earliest date (lexicographically on iso)
    earliest: Dict[str, Tuple[str, str]] = {}
    for r in all_rows:
        title = r.get("song_title")
        date_iso = r.get("album_release_date_iso") or ""
        if not title:
            continue
        if title not in earliest:
            earliest[title] = (date_iso, r.get("album_release_date_raw") or "")
        else:
            existing_iso, _ = earliest[title]
            if date_iso and (not existing_iso or date_iso < existing_iso):
                earliest[title] = (date_iso, r.get("album_release_date_raw") or "")

    with open(OUTPUT_UNIQUE, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["song_title", "album_release_date_iso"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for title, (iso, _) in sorted(earliest.items(), key=lambda x: (x[1][0] or "9999", x[0].lower())):
            w.writerow({"song_title": title, "album_release_date_iso": iso})

    print(f"Wrote {len(all_rows)} rows to {OUTPUT_ALL}")
    print(f"Wrote {len(earliest)} unique songs to {OUTPUT_UNIQUE}")


if __name__ == "__main__":
    main()
