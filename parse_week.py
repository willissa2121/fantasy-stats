#!/usr/bin/env python3
"""Parse a pasted Sleeper-style weekly matchup dump into JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCORE_RE = re.compile(r"^\d+\.\d{2}$")
PCT_RE = re.compile(r"^(\d+)%$")
RECORD_RE = re.compile(r"^(\d+)-(\d+)(?:-(\d+))?$")
HANDLE_RE = re.compile(r"^@(\S+)$")
WEEK_RE = re.compile(r"^Wk\.\s*(\d+)$", re.IGNORECASE)
WEEK_FILE_RE = re.compile(r"week-(\d+)", re.IGNORECASE)
SKIP_LINES = {"Matchups", "VS"}


def parse_record(text: str) -> dict[str, int]:
    match = RECORD_RE.match(text)
    if not match:
        raise ValueError(f"Expected W-L record, got {text!r}")
    record = {
        "wins": int(match.group(1)),
        "losses": int(match.group(2)),
    }
    ties = int(match.group(3) or 0)
    if ties:
        record["ties"] = ties
    return record


def parse_team(lines: list[str], start: int, badges: list[str]) -> tuple[dict[str, Any], int]:
    i = start
    handle_match = HANDLE_RE.match(lines[i])
    if not handle_match:
        raise ValueError(f"Expected @username at line {i + 1}: {lines[i]!r}")

    username = handle_match.group(1)
    i += 1
    if i >= len(lines):
        raise ValueError(f"Incomplete team block for @{username}")

    team_name = lines[i]
    i += 1
    if i >= len(lines) or not SCORE_RE.match(lines[i]):
        got = lines[i] if i < len(lines) else "end of file"
        raise ValueError(f"Expected score after {team_name!r}, got {got!r}")

    score = float(lines[i])
    i += 1

    # Win % is in the paste but not stored.
    if i < len(lines) and PCT_RE.match(lines[i]):
        i += 1

    record = None
    if i < len(lines) and RECORD_RE.match(lines[i]):
        record = parse_record(lines[i])
        i += 1

    # Projected score (or a duplicate of the actual score) is in the paste but not stored.
    if i < len(lines) and SCORE_RE.match(lines[i]):
        i += 1

    team: dict[str, Any] = {
        "username": username,
        "team_name": team_name,
        "score": score,
    }
    if record is not None:
        team["record"] = record
    if badges:
        team["badges"] = badges
    return team, i - start


def build_matchup(teams: list[dict[str, Any]]) -> dict[str, Any]:
    if not teams:
        raise ValueError("Matchup must have at least 1 team")

    matchup: dict[str, Any] = {"teams": teams}
    if len(teams) != 2:
        matchup["winner"] = None
        matchup["margin"] = None
        return matchup

    left, right = teams
    left_score = left["score"]
    right_score = right["score"]
    if left_score > right_score:
        winner = left["username"]
        margin = round(left_score - right_score, 2)
    elif right_score > left_score:
        winner = right["username"]
        margin = round(right_score - left_score, 2)
    else:
        winner = None
        margin = 0.0

    for team in teams:
        if winner is None:
            team["result"] = "tie"
        elif team["username"] == winner:
            team["result"] = "win"
        else:
            team["result"] = "loss"

    matchup["margin"] = margin
    matchup["winner"] = winner
    return matchup


def parse_week(
    text: str,
    season: int | None = None,
    week: int | None = None,
) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    i = 0
    matchups: list[dict[str, Any]] = []
    current_teams: list[dict[str, Any]] = []
    pending_badges: list[str] = []

    def flush_matchup() -> None:
        nonlocal current_teams
        if not current_teams:
            return
        matchups.append(build_matchup(current_teams))
        current_teams = []

    while i < len(lines):
        line = lines[i]
        if line == "Standings":
            break
        if line in SKIP_LINES:
            i += 1
            continue

        week_match = WEEK_RE.match(line)
        if week_match:
            week = int(week_match.group(1))
            i += 1
            continue

        if not HANDLE_RE.match(line):
            pending_badges.append(line)
            i += 1
            continue

        team, consumed = parse_team(lines, i, pending_badges)
        pending_badges = []
        i += consumed
        current_teams.append(team)
        if len(current_teams) == 2:
            flush_matchup()

    if current_teams:
        flush_matchup()

    return {
        "season": season,
        "week": week,
        "matchups": matchups,
    }


def season_from_path(path: Path) -> int | None:
    for part in path.parts:
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


def week_from_path(path: Path) -> int | None:
    match = WEEK_FILE_RE.search(path.name)
    return int(match.group(1)) if match else None


def write_json(dest: Path, payload: dict[str, Any]) -> None:
    dest.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def parse_file(source: Path) -> tuple[Path, dict[str, Any]] | None:
    text = source.read_text(encoding="utf-8")
    if not text.strip():
        print(f"Skipping empty {source}")
        return None

    payload = parse_week(
        text,
        season=season_from_path(source),
        week=week_from_path(source),
    )
    payload["source"] = str(source)
    return source.with_suffix(".json"), payload


def iter_teams(payload: dict[str, Any]):
    for matchup in payload.get("matchups", []):
        yield from matchup.get("teams", [])


def season_records(*payload_groups: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Build username -> record from weeks that still have a W-L line."""
    seen: dict[str, list[dict[str, int]]] = {}
    for payloads in payload_groups:
        for payload in payloads:
            for team in iter_teams(payload):
                record = team.get("record")
                if not record:
                    continue
                records = seen.setdefault(team["username"], [])
                if record not in records:
                    records.append(record)

    resolved: dict[str, dict[str, int]] = {}
    for username, records in seen.items():
        if len(records) == 1:
            resolved[username] = records[0]
            continue
        print(
            f"Warning: {username} has conflicting season records {records}; "
            "not inferring missing W-L",
            file=sys.stderr,
        )
    return resolved


def load_season_json(season_dir: Path, skip: set[Path]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    if not season_dir.is_dir():
        return payloads
    for path in season_dir.glob("week-*.json"):
        if path in skip:
            continue
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads


def backfill_records(
    payloads: list[dict[str, Any]],
    records: dict[str, dict[str, int]],
) -> int:
    filled = 0
    for payload in payloads:
        for team in iter_teams(payload):
            username = team.get("username")
            if "record" in team or username not in records:
                continue
            team["record"] = dict(records[username])
            filled += 1
    return filled


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        type=Path,
        nargs="+",
        help="Path(s) to pasted week-N.txt files",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="JSON output path (only valid with a single input)",
    )
    args = parser.parse_args()

    if args.output and len(args.input) != 1:
        parser.error("--output can only be used with a single input file")

    parsed: list[tuple[Path, dict[str, Any]]] = []
    failures = 0
    for source in args.input:
        try:
            result = parse_file(source)
        except Exception as exc:
            failures += 1
            print(f"Failed {source}: {exc}", file=sys.stderr)
            continue
        if result is None:
            continue
        dest, payload = result
        if args.output:
            dest = args.output
        parsed.append((dest, payload))

    by_season: dict[int | None, list[tuple[Path, dict[str, Any]]]] = {}
    for dest, payload in parsed:
        by_season.setdefault(payload.get("season"), []).append((dest, payload))

    for season, items in by_season.items():
        dests = {dest for dest, _ in items}
        payloads = [payload for _, payload in items]
        sibling_dir = items[0][0].parent
        siblings = load_season_json(sibling_dir, skip=dests)
        records = season_records(payloads, siblings)
        filled = backfill_records(payloads, records)
        if filled:
            print(f"Inferred {filled} missing record(s) for season {season}")

    for dest, payload in parsed:
        write_json(dest, payload)
        print(f"Wrote {dest} ({len(payload['matchups'])} matchups)")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
