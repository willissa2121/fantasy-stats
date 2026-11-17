#!/usr/bin/env python3
"""Parse per-player season schedule dumps into weekly matchup JSON."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from parse_week import build_matchup, season_from_path, write_json

LINE_RE = re.compile(
    r"^(?P<week>\d+)\s+logo\s+(?P<opp>.+?)\s+(?P<result>Win|Loss|Tie)\s+(?P<score>.+?)\s*$"
)
SCORE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d*)?)")


def parse_player_file(path: Path) -> dict[int, dict[str, Any]]:
    games: dict[int, dict[str, Any]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("Wk"):
            continue
        match = LINE_RE.match(line)
        if not match:
            raise ValueError(f"{path.name}: unparsed line {line!r}")
        score_match = SCORE_RE.search(match.group("score"))
        if not score_match:
            raise ValueError(f"{path.name}: bad score {line!r}")
        opp_raw = score_match.group(2)
        games[int(match.group("week"))] = {
            "opp_team": match.group("opp").strip(),
            "listed_result": match.group("result").lower(),
            "score": float(score_match.group(1)),
            "opp_score_raw": opp_raw,
            "opp_score": float(opp_raw) if opp_raw[-1].isdigit() else None,
        }
    return games


def scores_match(full: float, other_raw: str, other: float | None) -> bool:
    if other is not None and abs(full - other) < 0.001:
        return True
    formatted = f"{full:.2f}"
    return formatted.startswith(other_raw) or other_raw.startswith(formatted.rstrip("0").rstrip("."))


def filename_match_score(username: str, team: str) -> int:
    name = username.lower()
    team_l = team.lower()
    if name in team_l:
        return len(name)
    return 0


def infer_team_names(players: dict[str, dict[int, dict[str, Any]]]) -> dict[str, str]:
    votes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for left, left_games in players.items():
        for week, left_game in left_games.items():
            for right, right_games in players.items():
                if left == right or week not in right_games:
                    continue
                right_game = right_games[week]
                if scores_match(
                    left_game["score"],
                    right_game["opp_score_raw"],
                    right_game["opp_score"],
                ) and scores_match(
                    right_game["score"],
                    left_game["opp_score_raw"],
                    left_game["opp_score"],
                ):
                    votes[left][right_game["opp_team"]] += 1

    candidates: list[tuple[int, int, str, str]] = []
    for username, team_votes in votes.items():
        for team, count in team_votes.items():
            candidates.append(
                (-count, -filename_match_score(username, team), username, team)
            )
    candidates.sort()

    inferred: dict[str, str] = {}
    used_teams: set[str] = set()
    for _count, _match, username, team in candidates:
        if username in inferred or team in used_teams:
            continue
        inferred[username] = team
        used_teams.add(team)
    return inferred


def reconstruct_player(
    players: dict[str, dict[int, dict[str, Any]]],
    team_names: dict[str, str],
    username: str,
    team_name: str,
) -> None:
    invert = {"win": "loss", "loss": "win", "tie": "tie"}
    games: dict[int, dict[str, Any]] = {}
    for other, other_games in players.items():
        if other == username or other not in team_names:
            continue
        for week, game in other_games.items():
            if game["opp_team"] != team_name:
                continue
            if week in games:
                continue
            my_score = game["opp_score"]
            if my_score is None:
                my_score = float(game["opp_score_raw"] + "0")
            games[week] = {
                "opp_team": team_names[other],
                "listed_result": invert[game["listed_result"]],
                "score": my_score,
                "opp_score_raw": f"{game['score']:.2f}",
                "opp_score": game["score"],
            }
    if not games:
        raise ValueError(f"Could not reconstruct schedule for {username} ({team_name})")
    players[username] = games
    team_names[username] = team_name


def resolve_missing_players(
    players: dict[str, dict[int, dict[str, Any]]],
    team_names: dict[str, str],
) -> list[str]:
    warnings: list[str] = []
    unassigned = sorted(set(players) - set(team_names))
    known_teams = set(team_names.values())
    opponent_teams = {
        game["opp_team"]
        for user, games in players.items()
        if user in team_names
        for game in games.values()
    }
    missing_teams = sorted(opponent_teams - known_teams)
    if not unassigned and not missing_teams:
        return warnings
    if len(unassigned) != len(missing_teams):
        raise ValueError(
            f"Unassigned players {unassigned} do not match unmatched teams {missing_teams}"
        )

    remaining_teams = list(missing_teams)
    for username in unassigned:
        ranked = sorted(
            remaining_teams,
            key=lambda team: (-filename_match_score(username, team), team),
        )
        team = ranked[0]
        remaining_teams.remove(team)
        reconstruct_player(players, team_names, username, team)
        warnings.append(
            f"{username}.txt did not uniquely match a team; "
            f"reconstructed {team} from opponents"
        )
    return warnings


def season_record(games: dict[int, dict[str, Any]]) -> dict[str, int]:
    wins = sum(1 for game in games.values() if game["listed_result"] == "win")
    losses = sum(1 for game in games.values() if game["listed_result"] == "loss")
    ties = sum(1 for game in games.values() if game["listed_result"] == "tie")
    record = {"wins": wins, "losses": losses}
    if ties:
        record["ties"] = ties
    return record


def pair_week(
    week: int,
    players: dict[str, dict[int, dict[str, Any]]],
    team_names: dict[str, str],
    records: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    team_to_user = {team: user for user, team in team_names.items()}
    used: set[str] = set()
    matchups: list[dict[str, Any]] = []

    for username in sorted(players):
        if username in used:
            continue
        games = players[username]
        if week not in games:
            continue
        game = games[week]
        opponent = team_to_user.get(game["opp_team"])
        if opponent is None:
            raise ValueError(
                f"Week {week}: {username} played {game['opp_team']!r}, "
                "which does not match any player file"
            )
        if week not in players[opponent]:
            raise ValueError(f"Week {week}: {opponent} missing reverse matchup vs {username}")

        reverse = players[opponent][week]
        if reverse["opp_team"] != team_names[username]:
            raise ValueError(
                f"Week {week}: {username} vs {game['opp_team']} "
                f"but {opponent} listed {reverse['opp_team']}"
            )

        teams = [
            {
                "username": username,
                "team_name": team_names[username],
                "score": game["score"],
                "record": dict(records[username]),
            },
            {
                "username": opponent,
                "team_name": team_names[opponent],
                "score": reverse["score"],
                "record": dict(records[opponent]),
            },
        ]
        matchup = build_matchup(teams)
        for team, listed in (
            (teams[0], game["listed_result"]),
            (teams[1], reverse["listed_result"]),
        ):
            if team["result"] != listed:
                raise ValueError(
                    f"Week {week}: {team['username']} listed {listed} "
                    f"but score says {team['result']}"
                )
        matchups.append(matchup)
        used.add(username)
        used.add(opponent)

    expected = sorted(user for user, games in players.items() if week in games)
    if sorted(used) != expected:
        missing = sorted(set(expected) - used)
        raise ValueError(f"Week {week}: unmatched players {missing}")
    return matchups


def parse_season_dir(season_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    player_files = sorted(
        path
        for path in season_dir.glob("*.txt")
        if not path.name.startswith("week-") and path.read_text(encoding="utf-8").strip()
    )
    if not player_files:
        raise ValueError(f"No player schedule files in {season_dir}")

    players = {path.stem: parse_player_file(path) for path in player_files}

    signatures: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for user, games in players.items():
        sig = tuple(
            (week, game["opp_team"], game["listed_result"], game["score"], game["opp_score_raw"])
            for week, game in sorted(games.items())
        )
        signatures[sig].append(user)
    for users in signatures.values():
        if len(users) > 1:
            print(
                f"Warning: identical schedules in {', '.join(f'{u}.txt' for u in users)}",
                file=sys.stderr,
            )

    team_names = infer_team_names(players)
    for warning in resolve_missing_players(players, team_names):
        print(f"Warning: {warning}", file=sys.stderr)
    missing = sorted(set(players) - set(team_names))
    if missing:
        raise ValueError(f"Could not infer team names for: {', '.join(missing)}")

    records = {user: season_record(games) for user, games in players.items()}
    season = season_from_path(season_dir)
    weeks = sorted({week for games in players.values() for week in games})

    written: list[tuple[Path, dict[str, Any]]] = []
    for week in weeks:
        payload = {
            "season": season,
            "week": week,
            "matchups": pair_week(week, players, team_names, records),
            "source": str(season_dir),
        }
        written.append((season_dir / f"week-{week}.json", payload))
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "season_dir",
        type=Path,
        help="Directory of per-player schedule dumps (e.g. data/2024)",
    )
    args = parser.parse_args()

    try:
        written = parse_season_dir(args.season_dir)
    except Exception as exc:
        print(f"Failed {args.season_dir}: {exc}", file=sys.stderr)
        sys.exit(1)

    for dest, payload in written:
        write_json(dest, payload)
        print(f"Wrote {dest} ({len(payload['matchups'])} matchups)")


if __name__ == "__main__":
    main()
