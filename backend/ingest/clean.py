"""CSV cleaning for Gamepass_Games_v1.csv (REQ-001).

Standard-library only, so it runs and is unit-testable without the full app env.
Each field has a pure parse function; ``clean_csv`` orchestrates, dedupes, and reports.

The dirty reality (verified against the real CSV), and how we handle it:
  - GAMERS: thousands-separator strings ("84,143") and bare ("777"); 0 is a real value.
  - RATIO: float strings, but "-" for data-less rows (the 3 Shadowrun titles) -> None.
  - TIME:  ranges ("100-120 hours"), open bounds ("1000+ hours"), decimals ("0.5-1 hour"),
           and blanks -> None. We never invent a length we don't know.
  - RATING: 2.0-4.8 floats, blanks -> None (lowers metric contribution, never imputed).
  - ADDED: "06 Jan 22" dates, blanks, and the literal relative string "Yesterday" -> None.
  - Duplicates: exact dupes + platform/region variants ("(JP)", "(Xbox One)", ...) collapsed.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Field parsers (pure, individually testable)
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
# Trailing platform/region tags we strip for the dedup/match key. Conservative on
# purpose: we do NOT strip edition words here, so "Mass Effect Legendary Edition"
# stays distinct from "Mass Effect".
_PLATFORM_TAG_RE = re.compile(
    r"\s*\((?:xbox 360|xbox one|xbox|windows|pc|jp|us|eu)\)\s*$", re.IGNORECASE
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _blank(raw: str | None) -> bool:
    return raw is None or raw.strip() in ("", "-")


def parse_int_with_separators(raw: str | None) -> int | None:
    """GAMERS / achievement counts. '84,143' -> 84143, '777' -> 777, '0' -> 0, '-'/'' -> None."""
    if raw is None:
        return None
    s = raw.strip().replace(",", "").replace('"', "")
    if s == "" or s == "-":
        return None
    return int(round(float(s)))  # tolerate stray decimals defensively


def parse_ratio(raw: str | None) -> float | None:
    """RATIO. '1.87' -> 1.87; '-' or '' -> None (data-less rows)."""
    if _blank(raw):
        return None
    return float(raw.strip()) # type: ignore


def parse_float(raw: str | None) -> float | None:
    """COMP % / RATING. Keeps real 0.0; blank -> None (never imputed)."""
    if raw is None or raw.strip() == "":
        return None
    return float(raw.strip())


def parse_time(raw: str | None) -> tuple[float | None, float | None, float | None]:
    """TIME -> (min, max, midpoint) in hours.

    '100-120 hours' -> (100, 120, 110); '1000+ hours' -> (1000, None, 1000) [open bound];
    '0.5-1 hour' -> (0.5, 1.0, 0.75); '8-10 hours' -> (8, 10, 9); blank -> (None, None, None).
    """
    if raw is None:
        return (None, None, None)
    s = raw.strip().lower()
    if s == "":
        return (None, None, None)
    nums = [float(x) for x in _NUM_RE.findall(s)]
    if not nums:
        return (None, None, None)
    if "+" in s:  # open upper bound: midpoint falls back to the known lower bound
        return (nums[0], None, nums[0])
    if len(nums) == 1:
        return (nums[0], nums[0], nums[0])
    lo, hi = nums[0], nums[1]
    return (lo, hi, (lo + hi) / 2)


def parse_added(raw: str | None) -> date | None:
    """ADDED. '06 Jan 22' -> date(2022,1,6). Blank and the literal 'Yesterday' -> None."""
    if raw is None:
        return None
    s = raw.strip()
    if s == "" or s.lower() == "yesterday":
        return None
    try:
        return datetime.strptime(s, "%d %b %y").date()
    except ValueError:
        return None


def strip_platform_tag(title: str) -> str:
    """Drop a trailing platform/region tag like '(Xbox One)' or '(JP)'. Used both for the
    dedup key and as the cleaner search query for RAWG enrichment ('FIFA 21 (Xbox One)'
    searches better as 'FIFA 21'). Punctuation/case are preserved for the search path."""
    return _PLATFORM_TAG_RE.sub("", title.strip())


def normalize_title(title: str) -> str:
    """Dedup / enrichment-match key: lowercase, drop trailing platform/region tag,
    collapse punctuation. 'NBA 2K22 (Xbox One)' and 'NBA 2K22' -> 'nba 2k22'."""
    t = strip_platform_tag(title)
    t = _NON_ALNUM_RE.sub(" ", t.lower()).strip()
    return re.sub(r"\s+", " ", t)


# ---------------------------------------------------------------------------
# Record + orchestration
# ---------------------------------------------------------------------------

@dataclass
class CleanedGame:
    title: str
    normalized_title: str
    ratio: float | None
    gamers: int | None
    completion_pct: float | None
    time_min_hours: float | None
    time_max_hours: float | None
    time_midpoint: float | None
    rating: float | None
    added_date: date | None
    true_achievement: int | None
    game_score: int | None
    source_titles: list[str] = field(default_factory=list)

    def to_jsonable(self) -> dict:
        d = asdict(self)
        d["added_date"] = self.added_date.isoformat() if self.added_date else None
        return d


def clean_record(row: dict[str, str]) -> CleanedGame:
    """Clean one raw CSV row into a CleanedGame."""
    title = (row.get("GAME") or "").strip()
    lo, hi, mid = parse_time(row.get("TIME"))
    return CleanedGame(
        title=title,
        normalized_title=normalize_title(title),
        ratio=parse_ratio(row.get("RATIO")),
        gamers=parse_int_with_separators(row.get("GAMERS")),
        completion_pct=parse_float(row.get("COMP %")),
        time_min_hours=lo,
        time_max_hours=hi,
        time_midpoint=mid,
        rating=parse_float(row.get("RATING")),
        added_date=parse_added(row.get("ADDED")),
        true_achievement=parse_int_with_separators(row.get("True_Achievement")),
        game_score=parse_int_with_separators(row.get("Game_Score")),
        source_titles=[title],
    )


def _gamers_key(g: CleanedGame) -> int:
    # Sort key for the dedup "keep the richest variant" rule. Unknown count -> -1 so it ranks
    # *below* a real 0: a variant with any known player count wins over one with none.
    return g.gamers if g.gamers is not None else -1


def clean_csv(csv_path: str | Path) -> tuple[list[CleanedGame], dict]:
    """Read, clean, and dedupe the CSV. Returns (records, report).

    Dedup: group by normalized_title; keep the variant with the most GAMERS (most
    complete/popular), recording the merged raw titles in ``source_titles``.
    """
    raw_rows: list[dict[str, str]] = []
    # newline="" is required by the csv module (it handles quoted-field newlines itself);
    # utf-8-sig transparently strips the byte-order mark that Excel/Windows-exported CSVs
    # prepend — otherwise the first header reads back as "﻿GAME" and every lookup misses.
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if (row.get("GAME") or "").strip():  # skip the trailing empty line
                raw_rows.append(row)

    cleaned = [clean_record(r) for r in raw_rows]

    # Anomaly tracking (auditable, not silent).
    anomalies = {
        "ratio_missing": [c.title for c, r in zip(cleaned, raw_rows) if c.ratio is None],
        "rating_missing": [c.title for c, r in zip(cleaned, raw_rows) if c.rating is None],
        "time_missing": [c.title for c in cleaned if c.time_midpoint is None],
        "added_missing": [
            r.get("GAME", "").strip()
            for r in raw_rows
            if parse_added(r.get("ADDED")) is None
        ],
        "added_relative_yesterday": [
            r.get("GAME", "").strip()
            for r in raw_rows
            if (r.get("ADDED") or "").strip().lower() == "yesterday"
        ],
    }

    # Dedup by normalized_title, keeping the richest variant.
    by_key: dict[str, CleanedGame] = {}
    merges: list[dict] = []
    for g in cleaned:
        existing = by_key.get(g.normalized_title)
        if existing is None:
            by_key[g.normalized_title] = g
            continue
        keep, drop = (existing, g) if _gamers_key(existing) >= _gamers_key(g) else (g, existing)
        keep.source_titles = sorted(set(keep.source_titles) | set(drop.source_titles))
        by_key[g.normalized_title] = keep
        merges.append({"key": g.normalized_title, "kept": keep.title, "merged": keep.source_titles})

    deduped = list(by_key.values())
    report = {
        "raw_rows": len(raw_rows),
        "deduped_rows": len(deduped),
        "duplicates_collapsed": len(raw_rows) - len(deduped),
        "merges": merges,
        "anomaly_counts": {k: len(v) for k, v in anomalies.items()},
        "anomalies": anomalies,
    }
    return deduped, report


def main() -> None:
    ap = argparse.ArgumentParser(description="Clean Gamepass_Games_v1.csv (REQ-001).")
    default_csv = Path(__file__).resolve().parents[2] / "data" / "Gamepass_Games_v1.csv"
    ap.add_argument("--csv", type=Path, default=default_csv)
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "cleaned_games.json",
    )
    args = ap.parse_args()

    games, report = clean_csv(args.csv)
    args.out.write_text(
        json.dumps([g.to_jsonable() for g in games], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Read {report['raw_rows']} rows -> {report['deduped_rows']} unique games "
          f"({report['duplicates_collapsed']} duplicates collapsed).")
    print("Anomaly counts (kept as nulls, never imputed):")
    for k, v in report["anomaly_counts"].items():
        print(f"  {k:28} {v}")
    if report["merges"]:
        print("Merged variants:")
        for m in report["merges"]:
            print(f"  {m['kept']!r}  <-  {m['merged']}")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
