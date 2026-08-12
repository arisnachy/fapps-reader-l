from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import requests

OUT = Path("artifacts/kira_mlb_team_runs_dev_2012")
URL = "https://statsapi.mlb.com/api/v1/schedule"
PARAMS = {"sportId": 1, "season": 2012, "gameType": "R"}
EXPECTED_SOURCE_SHA256 = "59bf8c3469da6bfd58d9ffab742f6ddcb6d17f5aed64c46617bf334b558a7e5b"
FINAL_CODES = {"F", "FR"}
LINES = (3.5, 4.5)
SIDES = ("OVER", "UNDER")
LOOKBACKS = (10, 20)
TEAM_CUTS = (0.80, 0.90, 1.00)
OPP_CUTS = (0.70, 0.80, 0.90)
DEV_MIN_N = 50
DEV_MIN_LCB = 0.85


@dataclass(frozen=True)
class GameMeta:
    official_date: str
    game_pk: int
    home_id: int
    home_name: str
    away_id: int
    away_name: str


@dataclass(frozen=True)
class Outcome:
    home_runs: int
    away_runs: int


def wilson(wins: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = wins / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4.0 * n)) / n) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_2012() -> tuple[list[GameMeta], dict[int, Outcome], dict]:
    response = requests.get(URL, params=PARAMS, timeout=90, headers={"User-Agent": "KIRA-MLB-DEV/1.0"})
    response.raise_for_status()
    raw = response.content
    sha = hashlib.sha256(raw).hexdigest()
    if sha != EXPECTED_SOURCE_SHA256:
        raise SystemExit(f"SOURCE_SHA_MISMATCH expected={EXPECTED_SOURCE_SHA256} got={sha}")
    payload = response.json()

    meta_by_pk: dict[int, GameMeta] = {}
    outcomes: dict[int, Outcome] = {}
    duplicate_rows = 0
    duplicate_conflicts = []
    skipped_nonfinal = 0
    skipped_no_score = 0

    for date_row in payload.get("dates") or []:
        for game in date_row.get("games") or []:
            status = str(((game.get("status") or {}).get("statusCode")) or "")
            if status not in FINAL_CODES:
                skipped_nonfinal += 1
                continue
            pk = int(game["gamePk"])
            teams = game.get("teams") or {}
            home = teams.get("home") or {}
            away = teams.get("away") or {}
            if home.get("score") is None or away.get("score") is None:
                skipped_no_score += 1
                continue
            official_date = str(game.get("officialDate") or date_row.get("date") or "")
            hm = GameMeta(
                official_date=official_date,
                game_pk=pk,
                home_id=int((home.get("team") or {})["id"]),
                home_name=str((home.get("team") or {}).get("name") or ""),
                away_id=int((away.get("team") or {})["id"]),
                away_name=str((away.get("team") or {}).get("name") or ""),
            )
            out = Outcome(home_runs=int(home["score"]), away_runs=int(away["score"]))
            if pk in meta_by_pk:
                duplicate_rows += 1
                if meta_by_pk[pk] != hm or outcomes[pk] != out:
                    duplicate_conflicts.append(pk)
                continue
            meta_by_pk[pk] = hm
            outcomes[pk] = out

    if duplicate_conflicts:
        raise SystemExit(f"DUPLICATE_GAMEPK_CONFLICTS {duplicate_conflicts[:10]}")

    metas = sorted(meta_by_pk.values(), key=lambda g: (g.official_date, g.game_pk))
    if len(metas) != 2430:
        raise SystemExit(f"UNEXPECTED_UNIQUE_FINAL_GAMES {len(metas)} != 2430")
    audit = {
        "url": URL,
        "params": PARAMS,
        "bytes": len(raw),
        "sha256": sha,
        "unique_final_games": len(metas),
        "duplicate_schedule_rows_deduped": duplicate_rows,
        "duplicate_conflicts": len(duplicate_conflicts),
        "skipped_nonfinal_schedule_rows": skipped_nonfinal,
        "skipped_final_without_score": skipped_no_score,
        "first_date": metas[0].official_date,
        "last_date": metas[-1].official_date,
        "oos_2013_loaded": False,
    }
    return metas, outcomes, audit


def success(value: int, line: float, side: str) -> bool:
    return value > line if side == "OVER" else value < line


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    games, outcomes, source_audit = load_2012()

    # Histories contain only games from STRICTLY EARLIER official dates.
    # Each entry: (runs_for, runs_against).
    history: dict[int, list[tuple[int, int]]] = defaultdict(list)
    games_by_date: dict[str, list[GameMeta]] = defaultdict(list)
    for game in games:
        games_by_date[game.official_date].append(game)

    configs = [
        {
            "line": line,
            "side": side,
            "lookback_n": lookback,
            "team_cut": team_cut,
            "opp_cut": opp_cut,
        }
        for line in LINES
        for side in SIDES
        for lookback in LOOKBACKS
        for team_cut in TEAM_CUTS
        for opp_cut in OPP_CUTS
    ]
    if len(configs) != 72:
        raise SystemExit(f"CONFIG_COUNT_MISMATCH {len(configs)}")

    preselected: dict[int, list[dict]] = defaultdict(list)

    for official_date in sorted(games_by_date):
        date_games = sorted(games_by_date[official_date], key=lambda g: g.game_pk)

        # Candidate generation uses only prior-date history; target outcomes are not read here.
        for game in date_games:
            team_views = [
                (game.home_id, game.home_name, game.away_id, game.away_name, "HOME"),
                (game.away_id, game.away_name, game.home_id, game.home_name, "AWAY"),
            ]
            for config_id, cfg in enumerate(configs):
                eligible = []
                for team_id, team_name, opp_id, opp_name, venue_side in team_views:
                    n = int(cfg["lookback_n"])
                    if len(history[team_id]) < n or len(history[opp_id]) < n:
                        continue
                    team_recent = history[team_id][-n:]
                    opp_recent = history[opp_id][-n:]
                    team_rate = sum(success(rf, cfg["line"], cfg["side"]) for rf, _ in team_recent) / n
                    opp_allowed_rate = sum(success(ra, cfg["line"], cfg["side"]) for _, ra in opp_recent) / n
                    if team_rate + 1e-12 < cfg["team_cut"] or opp_allowed_rate + 1e-12 < cfg["opp_cut"]:
                        continue
                    strength_min = min(team_rate, opp_allowed_rate)
                    strength_mean = (team_rate + opp_allowed_rate) / 2.0
                    eligible.append({
                        "official_date": official_date,
                        "game_pk": game.game_pk,
                        "selected_team_id": team_id,
                        "selected_team": team_name,
                        "opponent_team_id": opp_id,
                        "opponent_team": opp_name,
                        "venue_side": venue_side,
                        "line": cfg["line"],
                        "side": cfg["side"],
                        "lookback_n": n,
                        "team_cut": cfg["team_cut"],
                        "opp_cut": cfg["opp_cut"],
                        "team_success_rate": team_rate,
                        "opponent_allowed_success_rate": opp_allowed_rate,
                        "strength_min": strength_min,
                        "strength_mean": strength_mean,
                    })
                if eligible:
                    chosen = sorted(
                        eligible,
                        key=lambda r: (-r["strength_min"], -r["strength_mean"], r["selected_team_id"]),
                    )[0]
                    preselected[config_id].append(chosen)

        # Only after every target on this date is generated do we read this date's outcomes to update history.
        for game in date_games:
            outcome = outcomes[game.game_pk]
            history[game.home_id].append((outcome.home_runs, outcome.away_runs))
            history[game.away_id].append((outcome.away_runs, outcome.home_runs))

    config_results = []
    settled_by_config: dict[int, list[dict]] = {}
    for config_id, cfg in enumerate(configs):
        rows = []
        for candidate in preselected.get(config_id, []):
            outcome = outcomes[candidate["game_pk"]]
            actual_runs = outcome.home_runs if candidate["venue_side"] == "HOME" else outcome.away_runs
            hit = success(actual_runs, cfg["line"], cfg["side"])
            rows.append({**candidate, "actual_selected_team_runs": actual_runs, "hit": bool(hit)})
        settled_by_config[config_id] = rows
        n = len(rows)
        wins = sum(row["hit"] for row in rows)
        lcb, ucb = wilson(wins, n)
        date_counts = Counter(row["official_date"] for row in rows)
        team_counts = Counter(row["selected_team"] for row in rows)
        month_counts = Counter(row["official_date"][:7] for row in rows)
        config_results.append({
            "config_id": config_id,
            **cfg,
            "n_selected": n,
            "wins": wins,
            "losses": n - wins,
            "hit_rate": wins / n if n else 0.0,
            "wilson95_lcb": lcb,
            "wilson95_ucb": ucb,
            "candidate_dates": len(date_counts),
            "mean_candidates_per_candidate_date": n / len(date_counts) if date_counts else 0.0,
            "max_candidates_one_date": max(date_counts.values()) if date_counts else 0,
            "max_team": team_counts.most_common(1)[0][0] if team_counts else "",
            "max_team_n": team_counts.most_common(1)[0][1] if team_counts else 0,
            "max_month": month_counts.most_common(1)[0][0] if month_counts else "",
            "max_month_n": month_counts.most_common(1)[0][1] if month_counts else 0,
            "dev_advance_eligible": n >= DEV_MIN_N and lcb >= DEV_MIN_LCB,
        })

    eligible = [r for r in config_results if r["dev_advance_eligible"]]
    winner = None
    if eligible:
        winner = sorted(
            eligible,
            key=lambda r: (
                -r["wilson95_lcb"],
                -r["n_selected"],
                -r["hit_rate"],
                -r["lookback_n"],
                -r["team_cut"],
                -r["opp_cut"],
                r["line"],
                r["side"],
            ),
        )[0]

    config_results_sorted = sorted(
        config_results,
        key=lambda r: (-r["wilson95_lcb"], -r["n_selected"], -r["hit_rate"], r["config_id"]),
    )
    write_csv(OUT / "all_72_config_results.csv", config_results_sorted)
    (OUT / "source_audit.json").write_text(json.dumps(source_audit, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "hypothesis_family": "MLB_TEAM_RUNS_HALF_LINE_V1",
        "dev_season": 2012,
        "oos_2013_loaded_or_scored": False,
        "config_count": len(config_results),
        "dev_min_n": DEV_MIN_N,
        "dev_min_lcb": DEV_MIN_LCB,
        "dev_advance_eligible_config_count": len(eligible),
        "decision": "DEV_WINNER_READY_FOR_OOS_PREREGISTRATION" if winner else "NO_DEV_SIGNAL",
        "winner": winner,
        "source_sha256": source_audit["sha256"],
        "same_date_history_excluded": True,
        "same_event_max_one_selected_team": True,
        "one_pick_per_day_cap": False,
    }

    if winner:
        winner_rows = settled_by_config[winner["config_id"]]
        pre_rows = [
            {k: v for k, v in row.items() if k not in {"actual_selected_team_runs", "hit"}}
            for row in winner_rows
        ]
        write_csv(OUT / "winner_selected_keys_pre_settlement.csv", pre_rows)
        write_csv(OUT / "winner_selected_legs.csv", winner_rows)
        write_csv(OUT / "winner_failures.csv", [row for row in winner_rows if not row["hit"]])
        date_counts = Counter(row["official_date"] for row in winner_rows)
        team_counts = Counter(row["selected_team"] for row in winner_rows)
        (OUT / "winner_concentration.json").write_text(
            json.dumps({
                "date_counts": dict(sorted(date_counts.items())),
                "team_counts": dict(team_counts.most_common()),
            }, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    else:
        write_csv(OUT / "winner_selected_keys_pre_settlement.csv", [])
        write_csv(OUT / "winner_selected_legs.csv", [])
        write_csv(OUT / "winner_failures.csv", [])

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("TOP10_CONFIGS")
    print(json.dumps(config_results_sorted[:10], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
