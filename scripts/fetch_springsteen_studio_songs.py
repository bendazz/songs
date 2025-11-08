#!/usr/bin/env python3
import csv
import re
import time
from typing import Dict, List, Optional, Tuple

import musicbrainzngs as mb
from dateutil import parser as dateparser


APP_NAME = "songs-scraper"
APP_VERSION = "0.1"
APP_CONTACT = ""

ARTIST_NAME = "Bruce Springsteen"
USER_AGENT_DELAY_SEC = 1.1  # polite delay between API calls

# Secondary types that indicate non-studio albums to exclude
NON_STUDIO_SECONDARY_TYPES = {
    "Compilation",
    "Live",
    "Soundtrack",
    "Remix",
    "Spokenword",
    "Interview",
    "Audiobook",
    "DJ-mix",
    "Mixtape/Street",
    "Demo",
}

# Heuristic phrases to avoid selecting a deluxe/expanded edition as canonical
NON_STANDARD_HINTS = [
    "deluxe",
    "expanded",
    "anniversary",
    "remaster",
    "remastered",
    "reissue",
    "special edition",
    "collector",
    "bonus",
    "american land",
    "tour edition",
    "legacy edition",
]


def set_user_agent():
    mb.set_useragent(APP_NAME, APP_VERSION, APP_CONTACT)


def search_artist_mbid(name: str = ARTIST_NAME) -> str:
    """Get the exact artist MBID for the given name."""
    # Prefer browse via exact search; fallback to first exact name match
    result = mb.search_artists(artist=name, strict=True, limit=5)
    arts = result.get("artist-list", [])
    if not arts:
        # fallback non-strict
        result = mb.search_artists(artist=name, strict=False, limit=5)
        arts = result.get("artist-list", [])
    if not arts:
        raise RuntimeError(f"Artist not found: {name}")
    # Prefer exact name, score 100
    for a in arts:
        if a.get("name") == name:
            return a["id"]
    # else take top scored
    return arts[0]["id"]


def is_studio_release_group(rg: Dict) -> bool:
    if rg.get("primary-type") != "Album":
        return False
    sec_list = rg.get("secondary-type-list") or []
    # If any non-studio markers present, exclude
    if any(sec in NON_STUDIO_SECONDARY_TYPES for sec in sec_list):
        return False
    return True


def is_studio_release_group_strict(rg_payload: Dict) -> bool:
    """Stricter check using a full release-group payload from get_release_group_by_id."""
    rg = rg_payload
    if rg.get("primary-type") != "Album":
        return False
    sec_list = rg.get("secondary-type-list") or []
    if any(sec in NON_STUDIO_SECONDARY_TYPES for sec in sec_list):
        return False
    return True


def list_studio_release_groups(artist_mbid: str) -> List[Dict]:
    rgs: List[Dict] = []
    limit = 100
    offset = 0
    while True:
        resp = mb.browse_release_groups(artist=artist_mbid, includes=[], limit=limit, offset=offset)
        chunk = resp.get("release-group-list", [])
        for rg in chunk:
            if is_studio_release_group(rg):
                rgs.append(rg)
        if len(chunk) < limit:
            break
        offset += limit
        time.sleep(USER_AGENT_DELAY_SEC)
    return rgs


def parse_date_precision(d: str) -> Tuple[str, str]:
    """
    Return (iso_date, precision) from a MusicBrainz date string.
    For partial dates, we normalize to the first of the period for iso_date.
    - YYYY-MM-DD -> (YYYY-MM-DD, day)
    - YYYY-MM    -> (YYYY-MM-01, month)
    - YYYY       -> (YYYY-01-01, year)
    """
    if not d:
        return "", ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        return d, "day"
    if re.fullmatch(r"\d{4}-\d{2}", d):
        return f"{d}-01", "month"
    if re.fullmatch(r"\d{4}", d):
        return f"{d}-01-01", "year"
    # last resort: try parsing
    try:
        dt = dateparser.parse(d)
        return dt.date().isoformat(), "day"
    except Exception:
        return d, ""


def date_sort_key(d: str) -> Tuple[int, int, int]:
    """Sort key that handles partial dates by assuming earliest in period."""
    iso, _ = parse_date_precision(d)
    if not iso:
        return (9999, 12, 31)
    y, m, dd = iso.split("-")
    return (int(y), int(m), int(dd))


def pick_canonical_release(releases: List[Dict], group_title: str) -> Optional[Dict]:
    """Pick a canonical, standard release among the earliest official ones."""
    # Filter to Official
    official = [r for r in releases if r.get("status") == "Official"]
    if not official:
        return None
    # Sort by earliest date
    official.sort(key=lambda r: date_sort_key(r.get("date", "")))
    earliest_date = official[0].get("date", "")
    earliest_official = [r for r in official if r.get("date", "") == earliest_date]

    def is_non_standard(r: Dict) -> bool:
        title = (r.get("title") or "").lower()
        disamb = (r.get("disambiguation") or "").lower()
        text = f"{title} {disamb}"
        # direct substrings first
        if any(h in text for h in NON_STANDARD_HINTS):
            return True
        # generic 'edition' variants
        if re.search(r"\b(special|deluxe|anniversary|expanded|legacy|tour|american land) edition\b", text):
            return True
        return False

    # Prefer those whose title equals group title and non-standard hints absent
    strict = [r for r in earliest_official if (r.get("title") or "").lower() == (group_title or "").lower() and not is_non_standard(r)]
    if strict:
        return strict[0]
    # Next, any non-standard-hint-absent among earliest
    clean = [r for r in earliest_official if not is_non_standard(r)]
    if clean:
        return clean[0]
    # Fallback: first earliest
    return earliest_official[0]


def get_release_group_earliest_official_date(releases: List[Dict]) -> Tuple[str, str]:
    # among official releases, pick earliest date
    official = [r for r in releases if r.get("status") == "Official" and r.get("date")]
    if not official:
        return "", ""
    official.sort(key=lambda r: date_sort_key(r.get("date")))
    raw = official[0]["date"]
    iso, precision = parse_date_precision(raw)
    return iso, raw


def fetch_tracks_for_release(release_id: str) -> List[Dict]:
    info = mb.get_release_by_id(release_id, includes=["recordings"])
    rel = info["release"]
    rows: List[Dict] = []
    audio_formats = {
        None,
        "CD",
        "Digital Media",
        "12\" Vinyl",
        "10\" Vinyl",
        "7\" Vinyl",
        "Vinyl",
        "LP",
        "Cassette",
    }
    for medium in rel.get("medium-list", []):
        fmt = medium.get("format")
        if fmt not in audio_formats:
            # skip video-only mediums like DVD-Video, Blu-ray, etc.
            continue
        disc_no = int(medium.get("position", 1))
        for t in medium.get("track-list", []):
            track_no = int(t.get("number") or 0) if str(t.get("number")).isdigit() else None
            title = t.get("recording", {}).get("title") or t.get("title") or ""
            rec_id = t.get("recording", {}).get("id")
            rows.append({
                "disc_number": disc_no,
                "track_number": track_no,
                "song_title": title.strip(),
                "recording_mbid": rec_id,
            })
    return rows


def main(output_csv: str = "data/springsteen_studio_songs.csv"):
    set_user_agent()
    print("Searching artist MBID…")
    artist_mbid = search_artist_mbid(ARTIST_NAME)
    print(f"Artist MBID: {artist_mbid}")
    time.sleep(USER_AGENT_DELAY_SEC)

    print("Listing studio release-groups…")
    rgs = list_studio_release_groups(artist_mbid)
    print(f"Found {len(rgs)} candidate studio release-groups")
    time.sleep(USER_AGENT_DELAY_SEC)

    rows: List[Dict] = []
    for i, rg in enumerate(sorted(rgs, key=lambda x: x.get("first-release-date") or "9999")):
        rgid = rg["id"]
        rg_title = rg.get("title")
        print(f"[{i+1}/{len(rgs)}] {rg_title} ({rgid})")
        info = mb.get_release_group_by_id(rgid, includes=["releases"])  # full payload with types
        rg_full = info["release-group"]
        # Strict studio filter
        if not is_studio_release_group_strict(rg_full):
            print("  Not a studio album; skipping")
            time.sleep(USER_AGENT_DELAY_SEC)
            continue
        releases = rg_full.get("release-list", [])
        if not releases:
            print("  No releases; skipping")
            time.sleep(USER_AGENT_DELAY_SEC)
            continue
        # earliest official date for the group
        iso_date, raw_date = get_release_group_earliest_official_date(releases)
        # canonical release selection
        canonical = pick_canonical_release(releases, rg_title)
        if not canonical:
            print("  No official releases; skipping")
            time.sleep(USER_AGENT_DELAY_SEC)
            continue
        release_id = canonical["id"]
        time.sleep(USER_AGENT_DELAY_SEC)
        # fetch tracks
        track_rows = fetch_tracks_for_release(release_id)
        for tr in track_rows:
            rows.append({
                "song_title": tr["song_title"],
                "album_title": rg_title,
                "album_release_date_raw": raw_date,
                "album_release_date_iso": iso_date,
                "disc_number": tr["disc_number"],
                "track_number": tr["track_number"],
                "release_group_mbid": rgid,
                "release_mbid": release_id,
                "recording_mbid": tr["recording_mbid"],
            })
        print(f"  Tracks: {len(track_rows)}")
        time.sleep(USER_AGENT_DELAY_SEC)

    # Ensure output dir
    import os
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    # Write CSV
    fieldnames = [
        "song_title",
        "album_title",
        "album_release_date_raw",
        "album_release_date_iso",
        "disc_number",
        "track_number",
        "release_group_mbid",
        "release_mbid",
        "recording_mbid",
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Wrote {len(rows)} rows to {output_csv}")


if __name__ == "__main__":
    main()
