from __future__ import annotations

import hashlib
import io
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

TARGET = date(2026, 8, 11)
SOURCE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_wnba_schedules/wnba_schedule_2026.parquet"
EXPECTED_SHA256 = "3eb74d5e0ee9515d3dee8af644d58d0dc57e0121372e8caeb7445a2ec618eae5"
OUT = Path("wnba_c2_candidate_20260811.json")

JUANCITO_EVENTS = {
    frozenset(("New York Liberty", "Indiana Fever")): "1963368",
    frozenset(("Phoenix Mercury", "Los Angeles Sparks")): "1963377",
    frozenset(("Washington Mystics", "Las Vegas Aces")): "1963386",
}


def main() -> None:
    r = requests.get(SOURCE, timeout=120, headers={"User-Agent": "KIRA-WNBA-C2-FROZEN-2026/1.0"})
    r.raise_for_status()
    raw = r.content
    sha = hashlib.sha256(raw).hexdigest()
    if sha != EXPECTED_SHA256:
        raise SystemExit(f"SOURCE_SHA_MISMATCH {sha}")
    d = pd.read_parquet(io.BytesIO(raw))
    cols = [
        "game_date", "season_type", "status_type_completed",
        "home_display_name", "away_display_name", "home_score", "away_score",
    ]
    d = d[cols].copy()
    d["dt"] = pd.to_datetime(d["game_date"], errors="coerce", utc=True)
    d["day"] = d["dt"].dt.date
    d["season_type_n"] = pd.to_numeric(d["season_type"], errors="coerce")
    d["home_score_n"] = pd.to_numeric(d["home_score"], errors="coerce")
    d["away_score_n"] = pd.to_numeric(d["away_score"], errors="coerce")
    completed = d["status_type_completed"].astype(str).str.lower().isin(["true", "1"])
    reg = d[d["season_type_n"].eq(2) & d["dt"].notna()].copy()
    prior = reg[
        completed.loc[reg.index]
        & (reg["day"] < TARGET)
        & reg["home_score_n"].notna()
        & reg["away_score_n"].notna()
    ].sort_values("dt")
    today = reg[reg["day"] == TARGET].copy()

    scored = defaultdict(list)
    allowed = defaultdict(list)
    for _, g in prior.iterrows():
        h = str(g["home_display_name"])
        a = str(g["away_display_name"])
        hs = int(g["home_score_n"])
        aw = int(g["away_score_n"])
        scored[h].append(hs)
        scored[a].append(aw)
        allowed[h].append(aw)
        allowed[a].append(hs)

    candidates = []
    for _, g in today.iterrows():
        home = str(g["home_display_name"])
        away = str(g["away_display_name"])
        for team, opp in ((home, away), (away, home)):
            h = scored.get(team, [])
            oh = allowed.get(opp, [])
            if len(h) < 8 or len(oh) < 8:
                continue
            arr = np.asarray(h, float)
            o = np.asarray(oh, float)
            q10 = float(np.quantile(arr, .10, method="linear"))
            below = float(np.mean(arr < 55))
            last5 = float(np.mean(arr[-5:]))
            med = float(np.median(arr))
            opphold = float(np.mean(o < 55))
            eligible = q10 >= 59 and below <= .05 and last5 >= 65 and opphold <= .10
            if not eligible:
                continue
            event_id = JUANCITO_EVENTS.get(frozenset((team, opp)), "")
            candidates.append({
                "team": team,
                "opponent": opp,
                "event_source_id": event_id,
                "q10": q10,
                "below55_rate": below,
                "median_points": med,
                "last5_mean": last5,
                "opponent_hold_below55_rate": opphold,
                "prior_games_team": len(h),
                "prior_games_opponent": len(oh),
            })

    candidates.sort(key=lambda x: (-x["q10"], x["below55_rate"], -x["median_points"], -x["last5_mean"], x["team"]))
    selected = []
    for rank, row in enumerate(candidates[:2], 1):
        selected.append({
            **row,
            "rank": rank,
            "period": "full_game",
            "market_family": "team_total",
            "selection": "over",
            "compatible_lines": [54.5, 55.5, 56.5, 57.5],
            "settlement_status": "RULE_EQUIVALENCE_PENDING",
            "settlement_compatible": False,
        })

    result = {
        "status": "FROZEN_SELECTOR_RECONSTRUCTION_COMPLETE",
        "target_date": TARGET.isoformat(),
        "source_url": SOURCE,
        "source_sha256": sha,
        "source_expected_sha256": EXPECTED_SHA256,
        "prior_completed_regular_season_games": int(len(prior)),
        "target_date_regular_season_games": int(len(today)),
        "candidate_count_before_daily_cap": len(candidates),
        "max_daily_legs": 2,
        "selected": selected,
        "selection_rule": {
            "minimum_prior_games_team": 8,
            "minimum_prior_games_opponent": 8,
            "minimum_q10_points": 59,
            "maximum_prior_below55_rate": .05,
            "minimum_last5_mean_points": 65,
            "maximum_opponent_hold_below55_rate": .10,
            "ranking": ["q10_desc", "below55_rate_asc", "median_points_desc", "last5_mean_desc", "team_name_asc"],
        },
        "leakage_guard": "Target-date scores are never read or used for eligibility/ranking; only completed games strictly before 2026-08-11 feed features.",
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
