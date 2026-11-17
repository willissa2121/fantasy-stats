#!/usr/bin/env python3
"""Build docs/data/league.json from parsed weekly matchups."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "data" / "league.json"

PLAYERS = {
    "aj": {
        "name": "AJ",
        "aliases": ["aj", "AGarza509"],
    },
    "chris": {
        "name": "Chris",
        "aliases": ["chris", "ChrisThies"],
    },
    "corey": {
        "name": "Corey",
        "aliases": ["corey", "SlikkNuttington"],
    },
    "david": {
        "name": "David",
        "aliases": ["david", "Sauuuuucy"],
    },
    "derrick": {
        "name": "Derrick",
        "aliases": ["derrick", "dman98312"],
    },
    "jake": {
        "name": "Jake",
        "aliases": ["jake", "jakebuddyy"],
    },
    "jared": {
        "name": "Jared",
        "aliases": ["jared"],
    },
    "jesse": {
        "name": "Jesse",
        "aliases": ["jesse"],
    },
    "kelly": {
        "name": "Kelly",
        "aliases": ["kelly"],
    },
    "ken": {
        "name": "Ken",
        "aliases": ["ken"],
    },
    "luke": {
        "name": "Luke",
        "aliases": ["luke", "lukeypooky9"],
    },
    "mick": {
        "name": "Mick",
        "aliases": ["mick"],
    },
    "scott": {
        "name": "Scott",
        "aliases": ["scott", "spoderdude"],
    },
    "steve": {
        "name": "Steve",
        "aliases": ["steve"],
    },
    "unknown": {
        "name": "Unknown",
        "aliases": ["unknown"],
    },
    "wyatt": {
        "name": "Wyatt",
        "aliases": ["wyatt", "wyatt545454"],
    },
    "zach": {
        "name": "Zach",
        "aliases": ["zach", "ZachTodd94"],
    },
}

ALIAS_TO_ID = {
    alias: player_id
    for player_id, meta in PLAYERS.items()
    for alias in meta["aliases"]
}


def round2(value: float) -> float:
    return round(float(value), 2)


def pct(wins: int, games: int) -> float:
    if not games:
        return 0.0
    return round(wins / games, 3)


def summarize(games: list[dict]) -> dict:
    wins = sum(1 for game in games if game["result"] == "win")
    losses = sum(1 for game in games if game["result"] == "loss")
    ties = sum(1 for game in games if game["result"] == "tie")
    gp = len(games)
    pf = round2(sum(game["score"] for game in games))
    pa = round2(sum(game["opp_score"] for game in games))
    scores = [game["score"] for game in games]
    return {
        "gp": gp,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "record": f"{wins}-{losses}" + (f"-{ties}" if ties else ""),
        "win_pct": pct(wins, gp),
        "pf": pf,
        "pa": pa,
        "ppg": round2(pf / gp) if gp else 0.0,
        "papg": round2(pa / gp) if gp else 0.0,
        "diff": round2((pf - pa) / gp) if gp else 0.0,
        "high": round2(max(scores)) if scores else 0.0,
        "low": round2(min(scores)) if scores else 0.0,
    }


def load_games() -> tuple[list[int], dict[str, list[dict]]]:
    seasons: set[int] = set()
    by_player: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(DATA.glob("*/week-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        season = payload["season"]
        week = payload["week"]
        seasons.add(season)
        for matchup in payload.get("matchups", []):
            teams = matchup.get("teams") or []
            if len(teams) != 2:
                continue
            left, right = teams
            for team, opp in ((left, right), (right, left)):
                username = team.get("username")
                player_id = ALIAS_TO_ID.get(username)
                if not player_id:
                    raise ValueError(f"Unmapped username {username!r} in {path}")
                opp_id = ALIAS_TO_ID.get(opp.get("username"), opp.get("username"))
                result = team.get("result") or (
                    "win"
                    if team["score"] > opp["score"]
                    else "loss"
                    if team["score"] < opp["score"]
                    else "tie"
                )
                by_player[player_id].append(
                    {
                        "player_id": player_id,
                        "player_name": PLAYERS[player_id]["name"],
                        "season": season,
                        "week": week,
                        "team": team.get("team_name"),
                        "score": float(team["score"]),
                        "opp_id": opp_id,
                        "opp_name": PLAYERS.get(opp_id, {}).get("name", opp.get("username")),
                        "opp_team": opp.get("team_name"),
                        "opp_score": float(opp["score"]),
                        "margin": round2(abs(float(team["score"]) - float(opp["score"]))),
                        "result": result,
                    }
                )
    return sorted(seasons), by_player


def build() -> dict:
    seasons, games_by_player = load_games()
    players = []
    for player_id, meta in PLAYERS.items():
        games = sorted(
            games_by_player.get(player_id, []),
            key=lambda game: (game["season"], game["week"]),
        )
        if not games:
            continue
        season_stats = []
        for season in seasons:
            season_games = [game for game in games if game["season"] == season]
            if not season_games:
                continue
            stats = summarize(season_games)
            stats["season"] = season
            stats["team"] = season_games[-1]["team"]
            season_stats.append(stats)
        career = summarize(games)
        players.append(
            {
                "id": player_id,
                "name": meta["name"],
                "aliases": meta["aliases"],
                "first_season": games[0]["season"],
                "last_season": games[-1]["season"],
                "latest_team": games[-1]["team"],
                "career": career,
                "seasons": season_stats,
            }
        )
    players.sort(key=lambda player: (-player["career"]["gp"], player["name"]))
    current_season = seasons[-1]

    def latest_week(season: int) -> int:
        return max(
            (
                game["week"]
                for games in games_by_player.values()
                for game in games
                if game["season"] == season
            ),
            default=0,
        )

    active_ids = {
        player["id"] for player in players if player["last_season"] == current_season
    }
    active_games = {
        player_id: games
        for player_id, games in games_by_player.items()
        if player_id in active_ids
    }

    def awards_for(source: dict[str, list[dict]]) -> dict:
        return {
            "by_season": {
                str(season): build_awards(source, season, min_gp=4)
                for season in seasons
            },
            "all_time": build_awards(source, None, min_gp=20),
        }

    everyone = awards_for(games_by_player)
    active_only = awards_for(active_games)
    return {
        "league": {
            "name": "League History",
            "seasons": seasons,
            "current_season": current_season,
        },
        "players": players,
        "stats": {
            "current_season": current_season,
            "through_week": latest_week(current_season),
            "through_weeks": {str(season): latest_week(season) for season in seasons},
            "by_season": everyone["by_season"],
            "all_time": everyone["all_time"],
            "by_season_active": active_only["by_season"],
            "all_time_active": active_only["all_time"],
        },
    }


def player_rows(games_by_player: dict[str, list[dict]]) -> list[dict]:
    rows = []
    for player_id, games in games_by_player.items():
        if not games:
            continue
        stats = summarize(games)
        stats["id"] = player_id
        stats["name"] = PLAYERS[player_id]["name"]
        stats["games"] = sorted(games, key=lambda game: (game["season"], game["week"]))
        rows.append(stats)
    return rows


def longest_streak(games: list[dict], result: str) -> tuple[int, dict | None]:
    best = 0
    best_game = None
    run = 0
    for game in games:
        if game["result"] == result:
            run += 1
            if run > best:
                best = run
                best_game = game
        else:
            run = 0
    return best, best_game


TOP_N = 6


def award(title: str, blurb: str, entries: list[dict], group: str = "points") -> dict:
    return {
        "title": title,
        "blurb": blurb,
        "group": group,
        "entries": entries,
    }


def game_detail(game: dict) -> str:
    return f"Week {game['week']}, {game['season']} vs {game['opp_name']}"


def player_entry(row: dict, value: str, detail: str = "") -> dict:
    return {
        "player_id": row["id"],
        "player_name": row["name"],
        "value": value,
        "detail": detail,
    }


def game_entry(game: dict, value: str, detail: str = "") -> dict:
    return {
        "player_id": game["player_id"],
        "player_name": game["player_name"],
        "value": value,
        "detail": detail,
    }


def top_players(rows: list[dict], key, reverse: bool = True, n: int = TOP_N) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: ((-key(row) if reverse else key(row)), row["name"]),
    )[:n]


def top_games(games: list[dict], key, reverse: bool = True, n: int = TOP_N) -> list[dict]:
    return sorted(games, key=key, reverse=reverse)[:n]


def top_streaks(rows: list[dict], result: str, n: int = TOP_N) -> list[tuple[int, dict | None, dict]]:
    ranked = []
    for row in rows:
        length, game = longest_streak(row["games"], result)
        if length:
            ranked.append((length, game, row))
    ranked.sort(key=lambda item: (-item[0], item[2]["name"]))
    return ranked[:n]


def build_awards(
    games_by_player: dict[str, list[dict]],
    season: int | None,
    min_gp: int,
) -> list[dict]:
    scoped: dict[str, list[dict]] = {}
    for player_id, games in games_by_player.items():
        subset = [
            game
            for game in games
            if season is None or game["season"] == season
        ]
        if subset:
            scoped[player_id] = subset
    rows = player_rows(scoped)
    if not rows:
        return []
    rate_rows = [row for row in rows if row["gp"] >= min_gp] or rows
    games = [game for row in rows for game in row["games"]]
    wins = [game for game in games if game["result"] == "win"]
    losses = [game for game in games if game["result"] == "loss"]

    most_points = top_players(rows, lambda row: row["pf"])
    most_wins = top_players(rows, lambda row: row["wins"])
    most_losses = top_players(rows, lambda row: row["losses"])
    best_ppg = top_players(rate_rows, lambda row: row["ppg"])
    worst_ppg = top_players(rate_rows, lambda row: row["ppg"], reverse=False)
    best_pct = top_players(rate_rows, lambda row: row["win_pct"])
    worst_pct = top_players(rate_rows, lambda row: row["win_pct"], reverse=False)
    best_diff = top_players(rate_rows, lambda row: row["diff"])
    most_pa = top_players(rows, lambda row: row["pa"])
    high_games = top_games(games, lambda game: (game["score"], game["season"], game["week"]))
    low_games = top_games(
        games,
        lambda game: (game["score"], game["season"], game["week"]),
        reverse=False,
    )
    blowouts = top_games(wins, lambda game: (game["margin"], game["score"]))
    nailbiters = top_games(
        wins,
        lambda game: (game["margin"], -game["score"]),
        reverse=False,
    )
    heartbreaks = top_games(losses, lambda game: (game["score"], game["margin"]))
    heists = top_games(
        wins,
        lambda game: (game["score"], -game["margin"]),
        reverse=False,
    )
    streak_wins = top_streaks(rows, "win")
    streak_losses = top_streaks(rows, "loss")

    return [
        award(
            "Scoring title",
            "Most points scored",
            [
                player_entry(
                    row,
                    f"{row['pf']:.1f}",
                    f"{row['gp']} games · {row['ppg']:.1f} PPG",
                )
                for row in most_points
            ],
            "points",
        ),
        award(
            "Hot hand",
            "Highest points per game",
            [
                player_entry(row, f"{row['ppg']:.1f}", f"{row['gp']} games")
                for row in best_ppg
            ],
            "points",
        ),
        award(
            "High score",
            "Best single-week explosion",
            [
                game_entry(game, f"{game['score']:.1f}", game_detail(game))
                for game in high_games
            ],
            "points",
        ),
        award(
            "Brick layer",
            "Lowest points per game",
            [
                player_entry(row, f"{row['ppg']:.1f}", f"{row['gp']} games")
                for row in worst_ppg
            ],
            "points",
        ),
        award(
            "Floor",
            "Lowest single-week score",
            [
                game_entry(game, f"{game['score']:.1f}", game_detail(game))
                for game in low_games
            ],
            "points",
        ),
        award(
            "Punching bag",
            "Most points against",
            [
                player_entry(row, f"{row['pa']:.1f}", f"{row['papg']:.1f} PA/G")
                for row in most_pa
            ],
            "points",
        ),
        award(
            "Win machine",
            "Most wins",
            [player_entry(row, str(row["wins"]), row["record"]) for row in most_wins],
            "records",
        ),
        award(
            "Best record",
            "Highest win percentage",
            [
                player_entry(row, f"{row['win_pct'] * 100:.1f}%", row["record"])
                for row in best_pct
            ],
            "records",
        ),
        award(
            "Cellar",
            "Most losses",
            [player_entry(row, str(row["losses"]), row["record"]) for row in most_losses],
            "records",
        ),
        award(
            "Rough sledding",
            "Lowest win percentage",
            [
                player_entry(row, f"{row['win_pct'] * 100:.1f}%", row["record"])
                for row in worst_pct
            ],
            "records",
        ),
        award(
            "Point margin",
            "Best average differential",
            [
                player_entry(
                    row,
                    f"{row['diff']:+.1f}",
                    f"{row['ppg']:.1f} PPG / {row['papg']:.1f} PA/G",
                )
                for row in best_diff
            ],
            "margins",
        ),
        award(
            "Truck stick",
            "Biggest blowout win",
            [
                game_entry(
                    game,
                    f"+{game['margin']:.1f}",
                    f"{game['score']:.2f}–{game['opp_score']:.2f} · {game_detail(game)}",
                )
                for game in blowouts
            ],
            "margins",
        ),
        award(
            "Nail-biter",
            "Closest win",
            [
                game_entry(
                    game,
                    f"+{game['margin']:.2f}",
                    f"{game['score']:.2f}–{game['opp_score']:.2f} · {game_detail(game)}",
                )
                for game in nailbiters
            ],
            "margins",
        ),
        award(
            "On fire",
            "Longest win streak",
            [
                player_entry(
                    row,
                    str(length),
                    game_detail(game) if game else "",
                )
                for length, game, row in streak_wins
            ],
            "streaks",
        ),
        award(
            "Cold streak",
            "Longest losing streak",
            [
                player_entry(
                    row,
                    str(length),
                    game_detail(game) if game else "",
                )
                for length, game, row in streak_losses
            ],
            "streaks",
        ),
        award(
            "Heist",
            "Fewest points in a win",
            [
                game_entry(
                    game,
                    f"{game['score']:.2f}",
                    f"Beat {game['opp_name']} {game['score']:.2f}–{game['opp_score']:.2f}",
                )
                for game in heists
            ],
            "moments",
        ),
        award(
            "Heartbreak",
            "Most points in a loss",
            [
                game_entry(
                    game,
                    f"{game['score']:.2f}",
                    f"Lost to {game['opp_name']} {game['score']:.2f}–{game['opp_score']:.2f}",
                )
                for game in heartbreaks
            ],
            "moments",
        ),
    ]


def main() -> None:
    payload = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(payload['players'])} players, seasons {payload['league']['seasons']})")


if __name__ == "__main__":
    main()
