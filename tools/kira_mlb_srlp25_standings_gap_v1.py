from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

OUT = Path("artifacts/kira_mlb_srlp25_standings_gap_v1")
OUT.mkdir(parents=True, exist_ok=True)
API = "https://statsapi.mlb.com/api/v1/schedule"
USER_AGENT = "KIRA-MLB-SRLP25-STANDINGS-GAP-V1/1.0 read-only"

MIN_PRIOR_GAMES = 40
MIN_SELECTED_WPCT = 0.600
MAX_OPP_WPCT = 0.500
MIN_WPCT_GAP = 0.120
MIN_SELECTED_RDG = 0.50
MAX_LEGS_PER_DATE = 2
MIN_LEGS = 100
MIN_DATES = 60
MIN_RATE = 0.90  # policy is strictly > 90%, not >=

BLOCKS = [
    ("DEV_2022", 2022, date(2022, 3, 1), date(2022, 11, 15)),
    ("OOS_2023", 2023, date(2023, 3, 1), date(2023, 11, 15)),
]


def wilson(w: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = w / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return max(0.0, center - margin), min(1.0, center + margin)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
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


@dataclass
class TeamState:
    games: int = 0
    wins: int = 0
    losses: int = 0
    runs_for: int = 0
    runs_against: int = 0

    @property
    def wpct(self) -> float:
        return self.wins / self.games if self.games else 0.0

    @property
    def rdg(self) -> float:
        return (self.runs_for - self.runs_against) / self.games if self.games else 0.0


def iso_day(value: str) -> str:
    return str(value or "")[:10]


def month_windows(start: date, end: date):
    cur = date(start.year, start.month, 1)
    while cur <= end:
        if cur.month == 12:
            nxt = date(cur.year + 1, 1, 1)
        else:
            nxt = date(cur.year, cur.month + 1, 1)
        lo = max(start, cur)
        hi = min(end, date.fromordinal(nxt.toordinal() - 1))
        if lo <= hi:
            yield lo, hi
        cur = nxt


def fetch_block(year: int, start: date, end: date) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    games: dict[int, dict[str, Any]] = {}
    audit: list[dict[str, Any]] = []

    for lo, hi in month_windows(start, end):
        params = {
            "sportId": 1,
            "gameType": "R",
            "startDate": lo.strftime("%m/%d/%Y"),
            "endDate": hi.strftime("%m/%d/%Y"),
            "hydrate": "linescore",
        }
        response = session.get(API, params=params, timeout=60)
        response.raise_for_status()
        raw = response.content
        payload = response.json()
        audit.append({
            "year": year,
            "start": lo.isoformat(),
            "end": hi.isoformat(),
            "http": response.status_code,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "url_without_query_values": API,
        })
        for block in payload.get("dates") or []:
            for game in block.get("games") or []:
                try:
                    pk = int(game["gamePk"])
                except Exception:
                    continue
                games[pk] = game

    rows: list[dict[str, Any]] = []
    for pk, game in games.items():
        if str(game.get("gameType") or "") != "R":
            continue
        official = iso_day(game.get("officialDate") or game.get("gameDate"))
        if not official.startswith(str(year)):
            continue
        status = game.get("status") or {}
        if str(status.get("abstractGameState") or "").casefold() != "final":
            continue
        teams = game.get("teams") or {}
        away = teams.get("away") or {}
        home = teams.get("home") or {}
        try:
            away_id = int((away.get("team") or {})["id"])
            home_id = int((home.get("team") or {})["id"])
            away_name = str((away.get("team") or {})["name"])
            home_name = str((home.get("team") or {})["name"])
            away_score = int(away["score"])
            home_score = int(home["score"])
        except Exception:
            continue
        rows.append({
            "date": official,
            "game_pk": pk,
            "away_id": away_id,
            "away_name": away_name,
            "home_id": home_id,
            "home_name": home_name,
            "away_score": away_score,
            "home_score": home_score,
        })

    rows.sort(key=lambda r: (r["date"], r["game_pk"]))
    return rows, audit


def side_snapshot(state: TeamState) -> dict[str, Any]:
    return {
        "games": state.games,
        "wins": state.wins,
        "losses": state.losses,
        "runs_for": state.runs_for,
        "runs_against": state.runs_against,
        "wpct": state.wpct,
        "rdg": state.rdg,
    }


def candidate_from_game(game: dict[str, Any], states: dict[int, TeamState]) -> dict[str, Any] | None:
    """Pregame selector. Target-game scores are deliberately not accepted as inputs."""
    away_id = int(game["away_id"])
    home_id = int(game["home_id"])
    away = states[away_id]
    home = states[home_id]
    if away.games < MIN_PRIOR_GAMES or home.games < MIN_PRIOR_GAMES:
        return None

    possibilities = [
        (away_id, game["away_name"], home_id, game["home_name"], "AWAY", away, home),
        (home_id, game["home_name"], away_id, game["away_name"], "HOME", home, away),
    ]
    qualified = []
    for selected_id, selected_name, opp_id, opp_name, side, selected, opp in possibilities:
        gap = selected.wpct - opp.wpct
        if (
            selected.wpct >= MIN_SELECTED_WPCT
            and opp.wpct <= MAX_OPP_WPCT
            and gap >= MIN_WPCT_GAP
            and selected.rdg >= MIN_SELECTED_RDG
        ):
            qualified.append((selected_id, selected_name, opp_id, opp_name, side, selected, opp, gap))
    if len(qualified) != 1:
        return None

    selected_id, selected_name, opp_id, opp_name, side, selected, opp, gap = qualified[0]
    return {
        "date": game["date"],
        "game_pk": game["game_pk"],
        "away_id": away_id,
        "away_name": game["away_name"],
        "home_id": home_id,
        "home_name": game["home_name"],
        "selected_id": selected_id,
        "selected_name": selected_name,
        "opponent_id": opp_id,
        "opponent_name": opp_name,
        "selected_side": side,
        "selected_prior_games": selected.games,
        "opponent_prior_games": opp.games,
        "selected_prior_wpct": selected.wpct,
        "opponent_prior_wpct": opp.wpct,
        "prior_wpct_gap": gap,
        "selected_prior_rdg": selected.rdg,
        "opponent_prior_rdg": opp.rdg,
        "contract": "JUANCITO_MLB_SUPER_RUN_LINE_SELECTED_PLUS2_5",
    }


def rank_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda r: (
            -float(r["prior_wpct_gap"]),
            -float(r["selected_prior_rdg"]),
            -float(r["selected_prior_wpct"]),
            str(r["selected_name"]),
            str(r["opponent_name"]),
            int(r["game_pk"]),
        ),
    )[:MAX_LEGS_PER_DATE]
    return [{**row, "date_rank": idx} for idx, row in enumerate(ranked, 1)]


def update_states_for_day(day_games: list[dict[str, Any]], states: dict[int, TeamState]) -> None:
    for game in day_games:
        away = states[int(game["away_id"])]
        home = states[int(game["home_id"])]
        away_score = int(game["away_score"])
        home_score = int(game["home_score"])
        away.games += 1
        home.games += 1
        away.runs_for += away_score
        away.runs_against += home_score
        home.runs_for += home_score
        home.runs_against += away_score
        if away_score > home_score:
            away.wins += 1
            home.losses += 1
        elif home_score > away_score:
            home.wins += 1
            away.losses += 1
        else:
            raise RuntimeError(f"FINAL_MLB_TIE_UNEXPECTED gamePk={game['game_pk']}")


def select_block(games: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[int, dict[str, int]], dict[str, Any]]:
    states: dict[int, TeamState] = defaultdict(TeamState)
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outcomes: dict[int, dict[str, int]] = {}
    for game in games:
        by_date[str(game["date"])].append(game)
        outcomes[int(game["game_pk"])] = {
            "away_score": int(game["away_score"]),
            "home_score": int(game["home_score"]),
        }

    selected: list[dict[str, Any]] = []
    eligible_pre_cap = 0
    for day in sorted(by_date):
        day_games = sorted(by_date[day], key=lambda r: int(r["game_pk"]))
        candidates: list[dict[str, Any]] = []
        for game in day_games:
            pregame_view = {k: game[k] for k in ("date", "game_pk", "away_id", "away_name", "home_id", "home_name")}
            candidate = candidate_from_game(pregame_view, states)
            if candidate is not None:
                candidates.append(candidate)
        eligible_pre_cap += len(candidates)
        selected.extend(rank_candidates(candidates))
        # Only after every target game for the calendar date has been selected do
        # outcomes update the state used by future dates. Doubleheaders cannot leak.
        update_states_for_day(day_games, states)

    audit = {
        "eligible_pre_cap": eligible_pre_cap,
        "selected_legs": len(selected),
        "candidate_dates": len({r["date"] for r in selected}),
        "target_score_fields_available_to_selector": False,
        "same_day_results_update_same_day_selection": False,
        "max_legs_per_date": MAX_LEGS_PER_DATE,
    }
    return selected, outcomes, audit


def score_block(label: str, year: int, games: list[dict[str, Any]], source_audit: list[dict[str, Any]]) -> dict[str, Any]:
    block_dir = OUT / label.lower()
    block_dir.mkdir(parents=True, exist_ok=True)
    selected, outcomes, selection_audit = select_block(games)

    pre_path = block_dir / "selected_pre_settlement.csv"
    write_csv(pre_path, selected)
    pre_sha = hashlib.sha256(pre_path.read_bytes()).hexdigest()

    # Settlement is a separate pass over the immutable selected event keys.
    settled: list[dict[str, Any]] = []
    for row in selected:
        outcome = outcomes[int(row["game_pk"])]
        selected_score = outcome["away_score"] if row["selected_side"] == "AWAY" else outcome["home_score"]
        opponent_score = outcome["home_score"] if row["selected_side"] == "AWAY" else outcome["away_score"]
        margin = selected_score - opponent_score
        hit = margin >= -2
        settled.append({
            **row,
            "selected_score": selected_score,
            "opponent_score": opponent_score,
            "selected_margin": margin,
            "hit": hit,
        })

    write_csv(block_dir / "settled_legs.csv", settled)
    write_csv(block_dir / "failures.csv", [r for r in settled if not r["hit"]])

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in settled:
        grouped[str(row["date"])].append(row)
    bundles: list[dict[str, Any]] = []
    for day, rows in sorted(grouped.items()):
        rows = sorted(rows, key=lambda r: int(r["date_rank"]))
        bundles.append({
            "date": day,
            "legs": len(rows),
            "survived": all(bool(r["hit"]) for r in rows),
            "game_pks": "|".join(str(r["game_pk"]) for r in rows),
        })
    write_csv(block_dir / "daily_bundles.csv", bundles)
    write_csv(block_dir / "bundle_failures.csv", [r for r in bundles if not r["survived"]])

    n_legs = len(settled)
    leg_wins = sum(bool(r["hit"]) for r in settled)
    n_dates = len(bundles)
    bundle_wins = sum(bool(r["survived"]) for r in bundles)
    leg_lcb, leg_ucb = wilson(leg_wins, n_legs)
    bundle_lcb, bundle_ucb = wilson(bundle_wins, n_dates)
    leg_rate = leg_wins / n_legs if n_legs else 0.0
    bundle_rate = bundle_wins / n_dates if n_dates else 0.0

    gates = {
        "legs_n_ge_100": n_legs >= MIN_LEGS,
        "dates_n_ge_60": n_dates >= MIN_DATES,
        "leg_rate_gt_90": leg_rate > MIN_RATE,
        "leg_wilson_lcb_gt_90": leg_lcb > MIN_RATE,
        "bundle_rate_gt_90": bundle_rate > MIN_RATE,
        "bundle_wilson_lcb_gt_90": bundle_lcb > MIN_RATE,
        "temporal_firewall": selection_audit["target_score_fields_available_to_selector"] is False and selection_audit["same_day_results_update_same_day_selection"] is False,
        "one_event_one_leg": len({int(r["game_pk"]) for r in settled}) == n_legs,
        "max_two_per_date": all(int(r["legs"]) <= MAX_LEGS_PER_DATE for r in bundles),
        "complete_settlement": n_legs == len(selected),
    }
    passed = all(gates.values())
    summary = {
        "hypothesis_id": "MLB_SRLP25_STANDINGS_GAP_V1",
        "block": label,
        "year": year,
        "status": "PASS" if passed else "NO_PASS",
        "selected_ledger_sha256": pre_sha,
        "eligible_pre_cap": selection_audit["eligible_pre_cap"],
        "selected_legs": n_legs,
        "leg_wins": leg_wins,
        "leg_losses": n_legs - leg_wins,
        "leg_rate": leg_rate,
        "leg_wilson95_lcb": leg_lcb,
        "leg_wilson95_ucb": leg_ucb,
        "candidate_dates": n_dates,
        "bundle_wins": bundle_wins,
        "bundle_losses": n_dates - bundle_wins,
        "bundle_rate": bundle_rate,
        "bundle_wilson95_lcb": bundle_lcb,
        "bundle_wilson95_ucb": bundle_ucb,
        "gates": gates,
        "selection_audit": selection_audit,
        "source_audit": source_audit,
        "frozen_thresholds": {
            "min_prior_games_both": MIN_PRIOR_GAMES,
            "selected_wpct_min": MIN_SELECTED_WPCT,
            "opponent_wpct_max": MAX_OPP_WPCT,
            "wpct_gap_min": MIN_WPCT_GAP,
            "selected_rdg_min": MIN_SELECTED_RDG,
            "max_legs_per_date": MAX_LEGS_PER_DATE,
            "contract": "selected team +2.5 runs",
        },
    }
    (block_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    overall: dict[str, Any] = {
        "hypothesis_id": "MLB_SRLP25_STANDINGS_GAP_V1",
        "preregistration": "prereg/MLB_SRLP25_STANDINGS_GAP_V1_2026-08-12.md",
        "blocks": [],
        "oos_opened": False,
    }

    dev_label, dev_year, dev_start, dev_end = BLOCKS[0]
    dev_games, dev_source = fetch_block(dev_year, dev_start, dev_end)
    dev = score_block(dev_label, dev_year, dev_games, dev_source)
    overall["blocks"].append(dev)
    if dev["status"] != "PASS":
        overall["decision"] = "DEV_NO_PASS_V1_CLOSED_OOS_UNOPENED"
        (OUT / "overall_summary.json").write_text(json.dumps(overall, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("KIRA_MLB_SRLP25", json.dumps(overall, ensure_ascii=False, sort_keys=True))
        return 0

    oos_label, oos_year, oos_start, oos_end = BLOCKS[1]
    overall["oos_opened"] = True
    oos_games, oos_source = fetch_block(oos_year, oos_start, oos_end)
    oos = score_block(oos_label, oos_year, oos_games, oos_source)
    overall["blocks"].append(oos)
    overall["decision"] = "OOS_CERTAINTY_PASS" if oos["status"] == "PASS" else "OOS_NO_PASS_V1_CLOSED"
    (OUT / "overall_summary.json").write_text(json.dumps(overall, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("KIRA_MLB_SRLP25", json.dumps(overall, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
