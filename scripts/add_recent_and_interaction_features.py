#!/usr/bin/env python3
"""Augment the date-song play matrix with recent-window pct and interaction features.

Inputs:
  data/springsteen_date_song_play_matrix.csv (must contain columns:
    song_title, play_date_iso, played, pct_played_prior, catalog_size_at_play_date)

Outputs:
  data/springsteen_date_song_play_matrix_aug.csv with extra columns:
    pct_played_recent_<window_days>
    interaction_pct_x_catalog = pct_played_prior * catalog_size_at_play_date

Window definition:
  For each song and date, consider prior rows for the same song with
  play_date in (date - window_days, date). pct_recent = 100 * (#plays in window) / (#eligible dates in window),
  where eligibility is simply the count of prior dates in the window for that song.
"""
import csv
import argparse
from collections import defaultdict, deque
from datetime import datetime, timedelta

IN_PATH = "data/springsteen_date_song_play_matrix.csv"
OUT_PATH = "data/springsteen_date_song_play_matrix_aug.csv"
DATE_FMT = "%Y-%m-%d"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=IN_PATH)
    p.add_argument("--output", default=OUT_PATH)
    p.add_argument("--window-days", type=int, default=180)
    return p.parse_args()


def parse_date(s):
    try:
        return datetime.strptime(s, DATE_FMT).date()
    except Exception:
        return None


def to_float(s):
    try:
        return float(s)
    except Exception:
        return None


def main():
    args = parse_args()
    window = timedelta(days=args.window_days)
    win_col = f"pct_played_recent_{args.window_days}"

    # Read all rows
    rows = []
    with open(args.input, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        header = r.fieldnames or []
        for row in r:
            rows.append(row)

    # Sort by date asc per song
    rows.sort(key=lambda r: (r.get("song_title", ""), r.get("play_date_iso", "")))

    # Sliding windows per song
    by_song_window = defaultdict(deque)  # deque of (date, played)

    # Compute new cols
    for row in rows:
        song = row.get("song_title", "")
        d = parse_date(row.get("play_date_iso", ""))
        if not song or not d:
            row[win_col] = ""
        else:
            dq = by_song_window[song]
            # Evict old entries outside window
            cutoff = d - window
            while dq and dq[0][0] <= cutoff:
                dq.popleft()
            # Stats on current window (prior only)
            eligible = len(dq)
            plays = sum(1 for (dd, pl) in dq if pl == "1" or pl == 1)
            pct_recent = (plays / eligible) * 100.0 if eligible > 0 else 0.0
            row[win_col] = f"{pct_recent:.2f}"
            # Push current row into window for subsequent rows
            played = row.get("played", "0")
            dq.append((d, played))
        # Interaction term
        pct = to_float(row.get("pct_played_prior"))
        cat = to_float(row.get("catalog_size_at_play_date"))
        row["interaction_pct_x_catalog"] = "" if pct is None or cat is None else f"{pct * cat:.4f}"

    # Write augmented CSV
    out_header = list(set(rows[0].keys())) if rows else []
    # Preserve original header order and append new columns at end
    base_header = header or []
    extra_cols = [c for c in [win_col, "interaction_pct_x_catalog"] if c not in base_header]
    final_header = base_header + extra_cols

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=final_header)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print("Wrote", args.output)


if __name__ == "__main__":
    main()
