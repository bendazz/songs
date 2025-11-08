# Bruce Springsteen studio songs dataset

This repository contains a reproducible script that fetches every track from Bruce Springsteen's studio albums and outputs a CSV with the album's earliest official release date per song, using the MusicBrainz API.

## What you get
- Output at `data/springsteen_studio_songs.csv`
- One row per track on a studio album (original standard editions; excludes live/compilations/soundtracks; filters out video-only discs)
- Columns:
	- song_title
	- album_title
	- album_release_date_raw
	- album_release_date_iso (best-effort normalization; partial dates mapped to first of period)
	- disc_number
	- track_number
	- release_group_mbid
	- release_mbid
	- recording_mbid

## How it works
- Identifies Bruce Springsteen by MusicBrainz artist MBID
- Enumerates album release-groups and filters to studio albums
- For each album, chooses the earliest official release as canonical (avoids deluxe/expanded editions when possible)
- Pulls audio tracklists (skips DVD/Blu-ray mediums)
- Writes the dataset to CSV

## Run it

Requires Python 3.10+.

```bash
pip install -r requirements.txt
python3 scripts/fetch_springsteen_studio_songs.py
```

The script is polite to the MusicBrainz API and sleeps briefly between requests; a full run typically takes under a minute.

## Notes and assumptions
- "Studio album" means MusicBrainz release-groups with primary type Album and without non-studio secondary types (Live, Compilation, Soundtrack, etc.).
- Canonical tracklists aim for original standard editions; heuristics avoid deluxe/expanded/tour/anniversary editions.
- Album release date is the earliest official date among releases in the release-group. We keep both the raw date and a normalized ISO date, plus an implied precision.
- Some border cases (e.g., outtake collections) depend on MusicBrainz typing. If you prefer a stricter or looser definition, tweak `is_studio_release_group_strict` and the non-standard heuristics in the script.

## File overview
- `scripts/fetch_springsteen_studio_songs.py` — main harvester script
- `requirements.txt` — dependencies (`musicbrainzngs`, `python-dateutil`)
- `data/springsteen_studio_songs.csv` — generated dataset

## Next ideas
- Optional cross-check against Wikipedia for album release dates and track counts; flag discrepancies.
- Add writers/credits via MusicBrainz work relationships to identify covers, at the cost of additional API calls.