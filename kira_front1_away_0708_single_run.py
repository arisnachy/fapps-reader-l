from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import statistics
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

HYPOTHESIS_ID = "FOOTBALL_PLUS1_5_AWAY_MARKET_DOMINANCE_V1"
SEASON = "0708"
LEAGUES = ["E0", "SP1", "D1", "I1", "F1", "N1", "P1", "SC0", "B1"]
THRESHOLD = 0.75
Z = 1.959963984540054
REQUIRED = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "B365H", "B365D", "B365A"]
BASE = "https://www.football-data.co.uk/mmz4281/0708/{league}.csv"
OUT = Path("front1_away_0708_output")


def parse_date(value: str) -> date:
    raw = (value or "").strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%d-%m-%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"UNPARSEABLE_DATE:{raw}")


def dec(value: str) -> float:
    x = float((value or "").strip())
    if not math.isfinite(x) or x <= 1.0:
        raise ValueError("INVALID_DECIMAL_ODDS")
    return x


def integer(value: str) -> int:
    x = float((value or "").strip())
    if not math.isfinite(x) or int(x) != x:
        raise ValueError("INVALID_SCORE")
    return int(x)


def novig(h: float, d: float, a: float) -> tuple[float, float]:
    qh, qd, qa = 1.0 / h, 1.0 / d, 1.0 / a
    denom = qh + qd + qa
    return qh / denom, qa / denom


def wilson(successes: int, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    phat = successes / n
    den = 1.0 + Z * Z / n
    center = phat + Z * Z / (2.0 * n)
    spread = Z * math.sqrt((phat * (1.0 - phat) + Z * Z / (4.0 * n)) / n)
    return (center - spread) / den, (center + spread) / den


def csv_text(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    raise UnicodeDecodeError("unknown", b"", 0, 1, "cannot decode")


def fetch_source(league: str) -> tuple[bytes, str]:
    url = BASE.format(league=league)
    req = urllib.request.Request(url, headers={"User-Agent": "KIRA-FRONT1-FROZEN-OOS/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read(), url


def event_key(e: dict) -> str:
    return "|".join([e["date"], e["league_code"], e["HomeTeam"], e["AwayTeam"]])


def select_one(events: list[dict], side: str) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    prob = "p_home_novig" if side == "HOME" else "p_away_novig"
    price = "B365H" if side == "HOME" else "B365A"
    eligible_by_date: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        if e[prob] >= THRESHOLD:
            eligible_by_date[e["date"]].append(e)
    selected = {}
    for day, rows in eligible_by_date.items():
        rows = sorted(rows, key=lambda e: (-e[prob], e[price], e["league_code"], e["HomeTeam"], e["AwayTeam"]))
        selected[day] = rows[0]
    return eligible_by_date, selected


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_fingerprints = {}
    source_audit = {"required_columns": REQUIRED, "sources": {}, "cross_source_duplicate_event_rows": 0}
    prematch_events: list[dict] = []
    outcomes: dict[str, dict] = {}
    all_keys: set[str] = set()
    duplicate_keys: list[str] = []

    for league in LEAGUES:
        raw, url = fetch_source(league)
        text = csv_text(raw)
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        missing = [c for c in REQUIRED if c not in headers]
        if missing:
            raise RuntimeError(f"SOURCE_INTEGRITY_FAIL:{league}:missing={missing}")
        raw_rows = 0
        valid_rows = 0
        bad_rows = []
        dates = []
        for idx, row in enumerate(reader, start=2):
            raw_rows += 1
            try:
                dt = parse_date(row["Date"])
                h, d, a = dec(row["B365H"]), dec(row["B365D"]), dec(row["B365A"])
                fthg, ftag = integer(row["FTHG"]), integer(row["FTAG"])
                home, away = row["HomeTeam"].strip(), row["AwayTeam"].strip()
                if not home or not away:
                    raise ValueError("EMPTY_TEAM")
                ph, pa = novig(h, d, a)
            except Exception as exc:
                bad_rows.append({"row": idx, "error": f"{type(exc).__name__}:{exc}"})
                continue
            e = {
                "date": dt.isoformat(),
                "league_code": league,
                "HomeTeam": home,
                "AwayTeam": away,
                "B365H": h,
                "B365D": d,
                "B365A": a,
                "p_home_novig": ph,
                "p_away_novig": pa,
            }
            key = event_key(e)
            if key in all_keys:
                duplicate_keys.append(key)
            all_keys.add(key)
            prematch_events.append(e)
            outcomes[key] = {"FTHG": fthg, "FTAG": ftag}
            dates.append(dt)
            valid_rows += 1
        if bad_rows:
            raise RuntimeError(f"SOURCE_INTEGRITY_FAIL:{league}:bad_rows={bad_rows[:5]} count={len(bad_rows)}")
        sha = hashlib.sha256(raw).hexdigest()
        source_fingerprints[league] = {"url": url, "sha256": sha, "bytes": len(raw)}
        source_audit["sources"][league] = {
            "url": url,
            "sha256": sha,
            "bytes": len(raw),
            "raw_rows": raw_rows,
            "valid_rows": valid_rows,
            "date_min": min(dates).isoformat() if dates else None,
            "date_max": max(dates).isoformat() if dates else None,
            "required_columns_present": True,
            "bad_rows": 0,
        }

    source_audit["cross_source_duplicate_event_rows"] = len(duplicate_keys)
    source_audit["duplicate_event_keys"] = duplicate_keys
    source_identity_pass = len(prematch_events) > 0 and len(duplicate_keys) == 0 and len(source_audit["sources"]) == len(LEAGUES)

    away_eligible, away_selected = select_one(prematch_events, "AWAY")
    home_eligible, home_selected = select_one(prematch_events, "HOME")

    # Outcome firewall: persist these fields before outcome join; FTHG/FTAG are intentionally absent.
    pre_fields = ["date", "league_code", "HomeTeam", "AwayTeam", "B365H", "B365D", "B365A", "p_away_novig"]
    pre_rows = [{k: e[k] for k in pre_fields} for _, e in sorted(away_selected.items())]
    write_csv(OUT / "selected_event_keys_pre_settlement.csv", pre_fields, pre_rows)

    selected_legs = []
    failures = []
    for day, e in sorted(away_selected.items()):
        key = event_key(e)
        score = outcomes[key]
        survived = score["FTAG"] + 1.5 > score["FTHG"]
        row = {
            **{k: e[k] for k in pre_fields},
            "FTHG": score["FTHG"],
            "FTAG": score["FTAG"],
            "selected_team": e["AwayTeam"],
            "contract": "AWAY +1.5",
            "settlement": "PASS" if survived else "FAIL",
            "loss_margin": score["FTHG"] - score["FTAG"],
        }
        selected_legs.append(row)
        if not survived:
            failures.append(row)

    leg_fields = pre_fields + ["FTHG", "FTAG", "selected_team", "contract", "settlement", "loss_margin"]
    write_csv(OUT / "selected_legs.csv", leg_fields, selected_legs)
    write_csv(OUT / "failures.csv", leg_fields, failures)

    n = len(selected_legs)
    successes = n - len(failures)
    rate = successes / n if n else 0.0
    lower, upper = wilson(successes, n)
    one_per_date = len(away_selected) == n == len({r["date"] for r in selected_legs})
    threshold_pass = all(float(r["p_away_novig"]) >= THRESHOLD for r in selected_legs)
    uniqueness_pass = len({event_key(r) for r in selected_legs}) == n
    settlement_complete = all(r["settlement"] in {"PASS", "FAIL"} for r in selected_legs)
    leakage_pass = all("FTHG" not in r and "FTAG" not in r for r in pre_rows)
    settlement_rule_pass = all((r["settlement"] == "FAIL") == (r["FTHG"] - r["FTAG"] >= 2) for r in selected_legs)

    team_counts = Counter(r["selected_team"] for r in selected_legs)
    league_counts = Counter(r["league_code"] for r in selected_legs)
    max_team = team_counts.most_common(1)[0] if team_counts else [None, 0]
    max_league = league_counts.most_common(1)[0] if league_counts else [None, 0]

    integrity = {
        "source_identity_pass": source_identity_pass,
        "one_selection_per_date_pass": one_per_date,
        "threshold_pass": threshold_pass,
        "selected_event_uniqueness_pass": uniqueness_pass,
        "settlement_completeness_pass": settlement_complete,
        "settlement_rule_pass": settlement_rule_pass,
        "result_leakage_firewall_pass": leakage_pass,
        "eligible_raw_events": sum(len(v) for v in away_eligible.values()),
        "selected_dates": n,
        "max_team": {"team": max_team[0], "count": max_team[1], "share": max_team[1] / n if n else 0},
        "max_league": {"league": max_league[0], "count": max_league[1], "share": max_league[1] / n if n else 0},
        "team_counts": dict(team_counts),
        "league_counts": dict(league_counts),
    }

    science_pass = all([
        source_identity_pass,
        one_per_date,
        threshold_pass,
        uniqueness_pass,
        settlement_complete,
        settlement_rule_pass,
        leakage_pass,
        n >= 35,
        lower >= 0.90,
    ])
    result = "PASS" if science_pass else "NO_PASS"
    summary = {
        "hypothesis_id": HYPOTHESIS_ID,
        "validation_block": SEASON,
        "execution_mode": "SINGLE_USE_FROZEN_OOS",
        "github_run_id": os.getenv("GITHUB_RUN_ID", ""),
        "threshold": THRESHOLD,
        "selected": n,
        "settled": n,
        "survived": successes,
        "failed": len(failures),
        "rate": rate,
        "wilson_z": Z,
        "wilson95_lower": lower,
        "wilson95_upper": upper,
        "n_gate": {"required": 35, "observed": n, "pass": n >= 35},
        "lcb_gate": {"required": 0.90, "observed": lower, "pass": lower >= 0.90},
        "integrity": integrity,
        "final_result": result,
        "classification_if_pass": "CORRELATED_FOOTBALL_AVAILABILITY_REDUNDANCY_NOT_INDEPENDENT_CORE",
        "anti_retune_guard": "Result is terminal for this preregistered 0708 block; no rule changes or reruns are permitted.",
    }

    # Outcome-blind HOME/AWAY comparable-calendar coverage on the same 0708 prematch source.
    active_dates = sorted({e["date"] for e in prematch_events})
    start = date.fromisoformat(active_dates[0])
    end = date.fromisoformat(active_dates[-1])
    calendar = []
    d = start
    while d <= end:
        ds = d.isoformat()
        hrows = home_eligible.get(ds, [])
        arows = away_eligible.get(ds, [])
        hs = home_selected.get(ds)
        ass = away_selected.get(ds)
        has_h, has_a = hs is not None, ass is not None
        category = "BOTH" if has_h and has_a else "HOME_ONLY" if has_h else "AWAY_ONLY" if has_a else "NEITHER"
        calendar.append({
            "date": ds,
            "match_active": ds in set(active_dates),
            "home_candidate_count": len(hrows),
            "home_selected_event": event_key(hs) if hs else "",
            "home_selected_entity": hs["HomeTeam"] if hs else "",
            "home_eligibility_state": "ELIGIBLE" if hs else "NO_ELIGIBLE_EVENT",
            "away_candidate_count": len(arows),
            "away_selected_event": event_key(ass) if ass else "",
            "away_selected_entity": ass["AwayTeam"] if ass else "",
            "away_eligibility_state": "ELIGIBLE" if ass else "NO_ELIGIBLE_EVENT",
            "coverage_category": category,
            "union_covered": has_h or has_a,
            "source_provenance": "official Football-Data 0708 B365H/B365D/B365A; outcome-blind",
        })
        d += timedelta(days=1)

    cal_fields = list(calendar[0].keys())
    write_csv(OUT / "home_away_eligibility_calendar_0708.csv", cal_fields, calendar)
    active_set = set(active_dates)
    active_rows = [r for r in calendar if r["date"] in active_set]
    cat_active = Counter(r["coverage_category"] for r in active_rows)
    cat_calendar = Counter(r["coverage_category"] for r in calendar)
    union_dates = [date.fromisoformat(r["date"]) for r in calendar if r["union_covered"]]
    gaps = [(b - a).days for a, b in zip(union_dates, union_dates[1:])]
    longest_none = 0
    current_none = 0
    for r in calendar:
        if not r["union_covered"]:
            current_none += 1
            longest_none = max(longest_none, current_none)
        else:
            current_none = 0
    coverage = {
        "block": SEASON,
        "comparison_is_outcome_blind": True,
        "thresholds_unchanged": {"HOME": 0.75, "AWAY": 0.75},
        "calendar_span": {"start": start.isoformat(), "end": end.isoformat(), "days": len(calendar)},
        "match_active_dates": len(active_rows),
        "home_candidate_dates": len(home_selected),
        "away_candidate_dates": len(away_selected),
        "active_date_categories": {
            "HOME_ONLY": cat_active["HOME_ONLY"],
            "AWAY_ONLY": cat_active["AWAY_ONLY"],
            "BOTH": cat_active["BOTH"],
            "NEITHER": cat_active["NEITHER"],
        },
        "calendar_day_categories": {
            "HOME_ONLY": cat_calendar["HOME_ONLY"],
            "AWAY_ONLY": cat_calendar["AWAY_ONLY"],
            "BOTH": cat_calendar["BOTH"],
            "NEITHER": cat_calendar["NEITHER"],
        },
        "union_candidate_dates": len(union_dates),
        "union_active_date_coverage_rate": len(union_dates) / len(active_rows) if active_rows else 0,
        "active_dates_no_bet": cat_active["NEITHER"],
        "active_date_no_bet_rate": cat_active["NEITHER"] / len(active_rows) if active_rows else 0,
        "calendar_days_no_bet": cat_calendar["NEITHER"],
        "calendar_day_no_bet_rate": cat_calendar["NEITHER"] / len(calendar) if calendar else 0,
        "median_days_between_union_candidate_dates": statistics.median(gaps) if gaps else None,
        "max_days_between_union_candidate_dates": max(gaps) if gaps else None,
        "longest_consecutive_calendar_days_without_candidate": longest_none,
        "incremental_away_fill_dates": cat_active["AWAY_ONLY"],
        "incremental_away_fill_share_of_home_gaps": cat_active["AWAY_ONLY"] / (cat_active["AWAY_ONLY"] + cat_active["NEITHER"]) if (cat_active["AWAY_ONLY"] + cat_active["NEITHER"]) else 0,
        "guard": "Coverage uses prematch prices and dates only; no FTHG/FTAG settlement outcome enters HOME/AWAY eligibility or overlap diagnostics.",
    }

    (OUT / "source_fingerprints.json").write_text(json.dumps(source_fingerprints, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "source_audit.json").write_text(json.dumps(source_audit, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "selection_settlement_audit.json").write_text(json.dumps(integrity, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "home_away_coverage_0708.json").write_text(json.dumps(coverage, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"summary": summary, "coverage": coverage}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
