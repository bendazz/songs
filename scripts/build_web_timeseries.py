#!/usr/bin/env python3
"""
Build per-song timeseries JSON for the web viz from the date-song matrix.

Reads data/springsteen_date_song_play_matrix.csv and outputs
web/data/song_pct.json with structure:
{
  "Thunder Road": [{"date":"1975-08-15","pct":12.34,"played":1}, ...],
  ...
}
- pct is pct_played_prior as a float (not string), missing values treated as 0.0.
- includes all rows for the song (eligible dates), ordered by date.
"""
import csv
import json
import os
from collections import defaultdict
from typing import Dict, List

MATRIX_CSV = "data/springsteen_date_song_play_matrix.csv"
OUT_JSON = "web/data/song_pct.json"
OUT_META = "web/data/song_meta.json"


def to_float(s: str) -> float:
    try:
        return float(s)
    except Exception:
        return 0.0


def main():
    series: Dict[str, List[Dict]] = defaultdict(list)
    with open(MATRIX_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            song = row.get("song_title") or ""
            date = row.get("play_date_iso") or ""
            pct = to_float(row.get("pct_played_prior") or "0")
            played = 1 if (row.get("played") == "1") else 0
            if not song or not date:
                continue
            series[song].append({"date": date, "pct": pct, "played": played})

    # Sort series by date
    for song, arr in series.items():
        arr.sort(key=lambda x: x["date"])

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(series, f)
    print(f"Wrote {len(series)} songs to {OUT_JSON}")

    # Also build a small metadata map (song -> album_release_date_iso) from the simplified CSV
    meta: Dict[str, str] = {}
    SIMPLE = "data/springsteen_songs_simple_unique.csv"
    if os.path.exists(SIMPLE):
        with open(SIMPLE, newline="", encoding="utf-8") as sf:
            r = csv.DictReader(sf)
            for row in r:
                title = row.get("song_title") or ""
                d = row.get("album_release_date_iso") or ""
                if title:
                    meta[title] = d
    else:
        print(f"Warning: {SIMPLE} not found; song_meta will be empty")

    with open(OUT_META, "w", encoding="utf-8") as mf:
        json.dump(meta, mf)
    print(f"Wrote metadata for {len(meta)} songs to {OUT_META}")


if __name__ == "__main__":
    main()
