#!/usr/bin/env python3
"""
Build a long-form date x song play matrix.

For each unique play date in the all-plays file, emit one row per catalog song
that was released on or before that date, with a played flag (1 if played that date, else 0).

Inputs:
- data/springsteen_songs_simple_unique.csv (song_title, album_release_date_iso)
- data/springsteen_songs_all_plays.csv or ..._with_years.csv (song_title, play_date_iso)

Output:
- data/springsteen_date_song_play_matrix.csv
    Columns: play_date_iso, song_title, album_release_date_iso, played, years_since_release, catalog_size_at_play_date, pct_played_prior

Assumption:
- A song is considered "eligible" on a date if its release date is on or before that date.
  If you prefer strictly before, change the comparison in eligible filtering.
"""
import csv
from datetime import date
from typing import Dict, List, Set, Tuple, Optional

INPUT_SONGS = "data/springsteen_songs_simple_unique.csv"
INPUT_PLAYS = "data/springsteen_songs_all_plays.csv"  # fallback if _with_years not present
INPUT_PLAYS_WITH_YEARS = "data/springsteen_songs_all_plays_with_years.csv"
OUTPUT_PATH = "data/springsteen_date_song_play_matrix.csv"


def parse_iso(d: str) -> Optional[date]:
    if not d:
        return None
    try:
        return date.fromisoformat(d)
    except Exception:
        return None


def load_songs(path: str) -> List[Tuple[str, date, str]]:
    out: List[Tuple[str, date, str]] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            title = row.get("song_title") or ""
            iso = row.get("album_release_date_iso") or ""
            dt = parse_iso(iso)
            if not title or not dt:
                # Skip songs without a valid release date
                continue
            out.append((title, dt, iso))
    return out


def load_plays(path: str) -> List[Tuple[str, date]]:
    out: List[Tuple[str, date]] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            title = row.get("song_title") or ""
            p_iso = row.get("play_date_iso") or ""
            p_dt = parse_iso(p_iso)
            if not title or not p_dt:
                continue
            out.append((title, p_dt))
    return out


def years_between(release_iso: str, play_iso: str) -> str:
    r = parse_iso(release_iso)
    p = parse_iso(play_iso)
    if not r or not p:
        return ""
    days = (p - r).days
    years = days / 365.2425
    return f"{years:.2f}"


def main():
    # pick plays input
    import os
    plays_path = INPUT_PLAYS_WITH_YEARS if os.path.exists(INPUT_PLAYS_WITH_YEARS) else INPUT_PLAYS

    songs = load_songs(INPUT_SONGS)
    plays = load_plays(plays_path)

    # Unique dates and songs-played-per-date
    unique_dates: List[date] = sorted({p_dt for _, p_dt in plays})
    played_on_date: Dict[date, Set[str]] = {}
    for title, p_dt in plays:
        played_on_date.setdefault(p_dt, set()).add(title)

    # Index dates for quick lookup
    date_index: Dict[date, int] = {d: i for i, d in enumerate(unique_dates)}

    # Precompute per-song cumulative played counts and eligible-date counts across the timeline
    # Eligibility is based on release date: dates >= release date
    songs_by_title: Dict[str, Tuple[date, str]] = {t: (dt, iso) for (t, dt, iso) in songs}
    cum_play_inclusive: Dict[str, List[int]] = {}
    cum_eligible_inclusive: Dict[str, List[int]] = {}

    for title, (rel_dt, _) in songs_by_title.items():
        cum_play = []
        cum_elig = []
        running_play = 0
        running_elig = 0
        for d in unique_dates:
            eligible = 1 if d >= rel_dt else 0
            running_elig += eligible
            played = 1 if title in played_on_date.get(d, set()) and eligible else 0
            running_play += played
            cum_play.append(running_play)
            cum_elig.append(running_elig)
        cum_play_inclusive[title] = cum_play
        cum_eligible_inclusive[title] = cum_elig

    # Precompute catalog size at each release date and per song (still available if needed)
    from collections import Counter
    date_counts: Dict[date, int] = {}
    for _, rel_dt, _ in songs:
        date_counts[rel_dt] = date_counts.get(rel_dt, 0) + 1
    cumulative_by_date: Dict[date, int] = {}
    running = 0
    for d_key in sorted(date_counts.keys()):
        running += date_counts[d_key]
        cumulative_by_date[d_key] = running
    catalog_size_by_song: Dict[str, int] = {}
    for title, rel_dt, _ in songs:
        catalog_size_by_song[title] = cumulative_by_date[rel_dt]

    # Precompute catalog size at each play date = number of songs released on/before that date
    # Use a two-pointer over songs sorted by release date
    songs_sorted_by_release = sorted(songs, key=lambda x: x[1])
    eligible_count_by_date: Dict[date, int] = {}
    idx = 0
    count = 0
    n = len(songs_sorted_by_release)
    for d_key in unique_dates:
        while idx < n and songs_sorted_by_release[idx][1] <= d_key:
            count += 1
            idx += 1
        eligible_count_by_date[d_key] = count

    # Build rows
    rows: List[Dict[str, str]] = []
    # For speed, pre-sort songs by release date
    songs_sorted = sorted(songs, key=lambda x: x[1])
    for d in unique_dates:
        played_titles = played_on_date.get(d, set())
        # Eligible songs: released on or before date 'd'
        for title, rel_dt, rel_iso in songs_sorted:
            if rel_dt <= d:
                played_flag = "1" if title in played_titles else "0"
                play_iso = d.isoformat()
                # Past (prior to this date) cumulative counts
                idx = date_index[d]
                if idx > 0:
                    prior_plays = cum_play_inclusive[title][idx - 1]
                    prior_eligible = cum_eligible_inclusive[title][idx - 1]
                else:
                    prior_plays = 0
                    prior_eligible = 0
                # Show 0.00 instead of blank when there are no prior eligible dates
                pct_played_prior = f"{(prior_plays / prior_eligible) * 100:.2f}" if prior_eligible > 0 else "0.00"
                rows.append({
                    "play_date_iso": play_iso,
                    "song_title": title,
                    "album_release_date_iso": rel_iso,
                    "played": played_flag,
                    "years_since_release": years_between(rel_iso, play_iso),
                    "catalog_size_at_play_date": str(eligible_count_by_date[d]),
                    "pct_played_prior": pct_played_prior,
                })

    # Write output
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "play_date_iso",
            "song_title",
            "album_release_date_iso",
            "played",
            "years_since_release",
            "catalog_size_at_play_date",
            "pct_played_prior",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Unique play dates: {len(unique_dates)}")
    print(f"Catalog songs with release dates: {len(songs)}")
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
