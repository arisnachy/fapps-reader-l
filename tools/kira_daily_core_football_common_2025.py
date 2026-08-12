from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

OUT = Path("artifacts/kira_daily_core_football_common_2025")
LEAGUES = ["E0", "SP1", "D1", "I1", "F1", "N1", "P1", "SC0", "B1"]
SEASONS = ["2425", "2526"]
WINDOW_START = date(2024, 12, 27)
WINDOW_END = date(2025, 12, 17)
REQUIRED = ["Date", "HomeTeam", "AwayTeam", "B365H", "B365D", "B365A"]


def parse_date(value):
    text = str(value).strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def historical_event_id(row):
    payload = "|".join(
        [row["date"], row["league_code"], row["HomeTeam"], row["AwayTeam"]]
    )
    return "FHIST-" + hashlib.sha256(payload.encode()).hexdigest()[:20]


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    source_audit = []
    valid_rows = []
    session = requests.Session()
    session.headers.update({"User-Agent": "KIRA-readonly-coverage-audit/1.0"})

    for season in SEASONS:
        for league in LEAGUES:
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
            response = session.get(url, timeout=30)
            if response.status_code != 200:
                raise SystemExit(f"SOURCE_MISSING {url} HTTP {response.status_code}")
            raw = response.content
            sha256 = hashlib.sha256(raw).hexdigest()
            parsed = None
            encoding_used = None
            for encoding in ("utf-8-sig", "latin-1"):
                try:
                    parsed = pd.read_csv(io.BytesIO(raw), encoding=encoding)
                    encoding_used = encoding
                    break
                except UnicodeDecodeError:
                    continue
            if parsed is None:
                raise SystemExit(f"UNREADABLE_SOURCE {url}")
            missing = [column for column in REQUIRED if column not in parsed.columns]
            if missing:
                raise SystemExit(f"REQUIRED_COLUMNS_MISSING {url} {missing}")

            accepted = 0
            bad_date = 0
            bad_odds = 0
            for _, row in parsed.iterrows():
                event_date = parse_date(row["Date"])
                if event_date is None:
                    bad_date += 1
                    continue
                if not (WINDOW_START <= event_date <= WINDOW_END):
                    continue
                try:
                    home_price = float(row["B365H"])
                    draw_price = float(row["B365D"])
                    away_price = float(row["B365A"])
                except (TypeError, ValueError):
                    bad_odds += 1
                    continue
                if not all(
                    math.isfinite(value) and value > 1.0
                    for value in (home_price, draw_price, away_price)
                ):
                    bad_odds += 1
                    continue
                home = str(row["HomeTeam"]).strip()
                away = str(row["AwayTeam"]).strip()
                if (
                    not home
                    or not away
                    or home.lower() == "nan"
                    or away.lower() == "nan"
                ):
                    continue

                q_home = 1.0 / home_price
                q_draw = 1.0 / draw_price
                q_away = 1.0 / away_price
                denominator = q_home + q_draw + q_away
                p_home = q_home / denominator
                p_draw = q_draw / denominator
                p_away = q_away / denominator
                valid_rows.append(
                    {
                        "date": event_date.isoformat(),
                        "season": season,
                        "league_code": league,
                        "HomeTeam": home,
                        "AwayTeam": away,
                        "B365H": home_price,
                        "B365D": draw_price,
                        "B365A": away_price,
                        "p_home_novig": p_home,
                        "p_draw_novig": p_draw,
                        "p_away_novig": p_away,
                    }
                )
                accepted += 1

            source_audit.append(
                {
                    "season": season,
                    "league_code": league,
                    "url": url,
                    "bytes": len(raw),
                    "sha256": sha256,
                    "raw_rows": len(parsed),
                    "accepted_pregame_rows_in_window": accepted,
                    "bad_date_rows_all_source": bad_date,
                    "bad_odds_rows_in_window": bad_odds,
                    "encoding": encoding_used,
                }
            )

    event_keys = [
        (row["date"], row["league_code"], row["HomeTeam"], row["AwayTeam"])
        for row in valid_rows
    ]
    duplicates = [key for key, count in Counter(event_keys).items() if count > 1]
    if duplicates:
        raise SystemExit(
            f"DUPLICATE_EVENT_KEYS {len(duplicates)} first={duplicates[:5]}"
        )

    # Frozen FOOTBALL_PLUS1_5_MARKET_DOMINANCE_V1 selector.
    home_by_date: dict[str, list[dict]] = {}
    for row in valid_rows:
        if row["p_home_novig"] >= 0.75:
            home_by_date.setdefault(row["date"], []).append(row)
    home_selected = []
    for _, items in sorted(home_by_date.items()):
        selected = sorted(
            items,
            key=lambda row: (
                -row["p_home_novig"],
                row["B365H"],
                row["league_code"],
                row["HomeTeam"],
                row["AwayTeam"],
            ),
        )[0]
        home_selected.append(
            {
                **selected,
                "strategy_id": "FOOTBALL_PLUS1_5_MARKET_DOMINANCE_V1",
                "sport": "football",
                "event_id": historical_event_id(selected),
                "selected_entity": selected["HomeTeam"],
                "opponent": selected["AwayTeam"],
                "selected_side": "HOME",
                "frozen_line": 1.5,
                "science_state": "SCIENCE/CERTAINTY PASS",
                "sports_candidate_frozen": True,
                "correlation_cluster": "CORRELATED_FOOTBALL_CLUSTER",
                "cluster_cap_one": True,
            }
        )

    # Frozen FOOTBALL_PLUS0_5_MARKET_FAVORITE_V1 selector.
    favorite_by_date: dict[str, list[dict]] = {}
    for row in valid_rows:
        p_home = row["p_home_novig"]
        p_away = row["p_away_novig"]
        if p_home == p_away:
            continue
        side = "HOME" if p_home > p_away else "AWAY"
        p_favorite = max(p_home, p_away)
        if p_favorite < 0.60:
            continue
        item = dict(row)
        item["p_favorite_novig"] = p_favorite
        item["selected_side"] = side
        item["selected_side_price"] = row["B365H"] if side == "HOME" else row["B365A"]
        item["selected_entity"] = row["HomeTeam"] if side == "HOME" else row["AwayTeam"]
        item["opponent"] = row["AwayTeam"] if side == "HOME" else row["HomeTeam"]
        favorite_by_date.setdefault(row["date"], []).append(item)

    favorite_selected = []
    for _, items in sorted(favorite_by_date.items()):
        selected = sorted(
            items,
            key=lambda row: (
                -row["p_favorite_novig"],
                row["selected_side_price"],
                row["league_code"],
                row["HomeTeam"],
                row["AwayTeam"],
                row["selected_side"],
            ),
        )[0]
        favorite_selected.append(
            {
                **selected,
                "strategy_id": "FOOTBALL_PLUS0_5_MARKET_FAVORITE_V1",
                "sport": "football",
                "event_id": historical_event_id(selected),
                "frozen_line": 0.5,
                "science_state": "SCIENCE/CERTAINTY PASS",
                "sports_candidate_frozen": True,
                "correlation_cluster": "CORRELATED_FOOTBALL_CLUSTER",
                "cluster_cap_one": True,
            }
        )

    home_map = {row["date"]: row for row in home_selected}
    favorite_map = {row["date"]: row for row in favorite_selected}
    active_dates = {row["date"] for row in valid_rows}
    daily = []
    cursor = WINDOW_START
    while cursor <= WINDOW_END:
        key = cursor.isoformat()
        home = home_map.get(key)
        favorite = favorite_map.get(key)
        if home and favorite:
            state = (
                "BOTH_SAME_EVENT"
                if home["event_id"] == favorite["event_id"]
                else "BOTH_DIFFERENT_EVENTS_CORRELATED_CLUSTER"
            )
        elif home:
            state = "HOME_ONLY"
        elif favorite:
            state = "FAVORITE_ONLY"
        else:
            state = "NEITHER"
        raw_ids = {
            candidate["event_id"]
            for candidate in (home, favorite)
            if candidate is not None
        }
        daily.append(
            {
                "date": key,
                "match_active": key in active_dates,
                "football_state": state,
                "home_candidate_event_id": home["event_id"] if home else "",
                "favorite_candidate_event_id": favorite["event_id"] if favorite else "",
                "raw_distinct_football_events": len(raw_ids),
                "conservative_football_legs": 1 if (home or favorite) else 0,
            }
        )
        cursor += timedelta(days=1)

    write_csv(OUT / "football_home_plus1_5_candidates.csv", home_selected)
    write_csv(OUT / "football_favorite_plus0_5_candidates.csv", favorite_selected)
    write_csv(OUT / "football_daily_coverage.csv", daily)
    (OUT / "source_audit.json").write_text(
        json.dumps(source_audit, indent=2, sort_keys=True), encoding="utf-8"
    )

    states = Counter(row["football_state"] for row in daily)
    active_states = Counter(row["football_state"] for row in daily if row["match_active"])
    union_days = sum(row["conservative_football_legs"] for row in daily)
    raw_two = sum(row["raw_distinct_football_events"] >= 2 for row in daily)
    summary = {
        "audit": "DAILY_CORE_FOOTBALL_COMMON_WINDOW_2025_OUTCOME_BLIND",
        "window_start": WINDOW_START.isoformat(),
        "window_end": WINDOW_END.isoformat(),
        "calendar_days": len(daily),
        "valid_pregame_events": len(valid_rows),
        "source_files": len(source_audit),
        "source_leagues": LEAGUES,
        "source_seasons": SEASONS,
        "home_plus1_5_candidate_dates": len(home_selected),
        "favorite_plus0_5_candidate_dates": len(favorite_selected),
        "football_union_candidate_dates_conservative": union_days,
        "football_union_calendar_coverage_pct": 100.0 * union_days / len(daily),
        "calendar_states": dict(states),
        "match_active_dates": sum(row["match_active"] for row in daily),
        "active_date_states": dict(active_states),
        "dates_with_two_raw_distinct_football_events": raw_two,
        "correlation_policy": "both PASS football strategies belong to CORRELATED_FOOTBALL_CLUSTER and count max one conservative leg/date",
        "outcome_columns_loaded_or_used": False,
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
