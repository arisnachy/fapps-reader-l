from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

OUT = Path("artifacts/kira_football_multi3_0304")
SEASON = "0304"
LEAGUES = ["E0", "SP1", "D1", "I1", "F1", "N1", "P1", "SC0", "B1"]
REQ = ["Date", "HomeTeam", "AwayTeam", "B365H", "B365D", "B365A", "FTHG", "FTAG"]
MIN_SOURCE_LEAGUES = 5
MIN_N = 35
MIN_LCB = 0.90


def wilson(w, n, z=1.959963984540054):
    if n <= 0:
        return 0.0, 1.0
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / d
    return max(0.0, c - m), min(1.0, c + m)


def parse_date(value):
    text = str(value).strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def decode(raw):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    raise ValueError("DECODE_FAILED")


def required_rows(raw):
    text, enc = decode(raw)
    parsed = list(csv.reader(io.StringIO(text)))
    while parsed and not any(str(x).strip() for x in parsed[0]):
        parsed.pop(0)
    if not parsed:
        return None, {"reason": "EMPTY", "encoding": enc}
    header = [str(x).strip() for x in parsed[0]]
    missing = [c for c in REQ if c not in header]
    if missing:
        return None, {"reason": "MISSING_COLUMNS", "missing": missing, "header_columns": len(header), "encoding": enc}
    indexes = {c: header.index(c) for c in REQ}
    max_required_index = max(indexes.values())
    rows = []
    extra = 0
    short = 0
    blanks = 0
    for raw_row in parsed[1:]:
        if not any(str(x).strip() for x in raw_row):
            blanks += 1
            continue
        if len(raw_row) <= max_required_index:
            short += 1
            continue
        if len(raw_row) > len(header):
            extra += 1
        rows.append({c: raw_row[i] for c, i in indexes.items()})
    if short:
        return None, {
            "reason": "ROW_SHORTER_THAN_REQUIRED_INDEX",
            "short_rows": short,
            "extra_trailing_field_rows": extra,
            "header_columns": len(header),
            "encoding": enc,
            "required_indices": indexes,
        }
    return rows, {
        "reason": "PASS",
        "extra_trailing_field_rows": extra,
        "blank_rows": blanks,
        "header_columns": len(header),
        "encoding": enc,
        "required_indices": indexes,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "KIRA-MULTI3-required-columns/1.0"
    source = []
    pregames = []
    outcomes = {}
    event_seen = set()
    duplicates = 0

    for league in LEAGUES:
        url = f"https://www.football-data.co.uk/mmz4281/{SEASON}/{league}.csv"
        try:
            response = session.get(url, timeout=30)
        except Exception as exc:
            source.append({"league": league, "url": url, "status": "SOURCE_UNUSABLE", "reason": type(exc).__name__})
            continue
        if response.status_code != 200:
            source.append({"league": league, "url": url, "http": response.status_code, "status": "SOURCE_UNUSABLE", "reason": "HTTP"})
            continue
        raw = response.content
        sha = hashlib.sha256(raw).hexdigest()
        try:
            records, meta = required_rows(raw)
        except Exception as exc:
            source.append({"league": league, "url": url, "bytes": len(raw), "sha256": sha, "status": "SOURCE_UNUSABLE", "reason": type(exc).__name__})
            continue
        if records is None:
            source.append({"league": league, "url": url, "bytes": len(raw), "sha256": sha, "status": "SOURCE_UNUSABLE", **meta})
            continue

        accepted = 0
        invalid_required_values = 0
        for row in records:
            d = parse_date(row["Date"])
            home = str(row["HomeTeam"]).strip()
            away = str(row["AwayTeam"]).strip()
            try:
                h = float(row["B365H"])
                draw = float(row["B365D"])
                a = float(row["B365A"])
                hg = int(float(row["FTHG"]))
                ag = int(float(row["FTAG"]))
            except Exception:
                invalid_required_values += 1
                continue
            if not d or not home or not away or not all(math.isfinite(x) and x > 1.0 for x in (h, draw, a)):
                invalid_required_values += 1
                continue
            event_key = (d, league, home, away)
            if event_key in event_seen:
                duplicates += 1
                continue
            event_seen.add(event_key)
            qh, qd, qa = 1 / h, 1 / draw, 1 / a
            p_home = qh / (qh + qd + qa)
            event_id = "FHIST-" + hashlib.sha256("|".join(event_key).encode()).hexdigest()[:20]
            pregames.append({"date": d, "league_code": league, "HomeTeam": home, "AwayTeam": away, "B365H": h, "B365D": draw, "B365A": a, "p_home_novig": p_home, "event_id": event_id})
            outcomes[event_id] = {"FTHG": hg, "FTAG": ag}
            accepted += 1
        source.append({"league": league, "url": url, "http": response.status_code, "bytes": len(raw), "sha256": sha, "source_rows_projected": len(records), "accepted_rows": accepted, "invalid_required_value_rows": invalid_required_values, "status": "PASS", **meta})

    usable = sum(row.get("status") == "PASS" for row in source)
    if usable < MIN_SOURCE_LEAGUES:
        summary = {"decision": "SOURCE_GATE_FAIL", "usable_leagues": usable, "required": MIN_SOURCE_LEAGUES, "source_audit": source}
        (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (OUT / "source_audit.json").write_text(json.dumps(source, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 0
    if duplicates:
        raise SystemExit(f"CROSS_SOURCE_DUPLICATES={duplicates}")

    by_date = {}
    for row in pregames:
        if row["p_home_novig"] >= 0.75:
            by_date.setdefault(row["date"], []).append(row)
    selected = []
    for d, items in sorted(by_date.items()):
        top = sorted(items, key=lambda x: (-x["p_home_novig"], x["B365H"], x["league_code"], x["HomeTeam"], x["AwayTeam"]))[:3]
        for rank, row in enumerate(top, 1):
            selected.append({**row, "date_rank": rank})
    write_csv(OUT / "selected_event_keys_pre_settlement.csv", selected)

    settled = []
    for row in selected:
        outcome = outcomes[row["event_id"]]
        hit = outcome["FTHG"] + 1.5 > outcome["FTAG"]
        settled.append({**row, **outcome, "hit": hit, "margin": outcome["FTHG"] - outcome["FTAG"]})
    write_csv(OUT / "selected_legs.csv", settled)
    write_csv(OUT / "failures.csv", [r for r in settled if not r["hit"]])

    by_selected_date = {}
    for row in settled:
        by_selected_date.setdefault(row["date"], []).append(row)
    bundles = []
    for d, rows in sorted(by_selected_date.items()):
        bundles.append({"date": d, "legs": len(rows), "survived": all(r["hit"] for r in rows), "event_ids": "|".join(r["event_id"] for r in rows)})
    write_csv(OUT / "daily_bundles.csv", bundles)
    write_csv(OUT / "bundle_failures.csv", [r for r in bundles if not r["survived"]])

    n_leg = len(settled)
    w_leg = sum(r["hit"] for r in settled)
    n_bundle = len(bundles)
    w_bundle = sum(r["survived"] for r in bundles)
    leg_l, leg_u = wilson(w_leg, n_leg)
    bundle_l, bundle_u = wilson(w_bundle, n_bundle)
    team = Counter(r["HomeTeam"] for r in settled)
    league = Counter(r["league_code"] for r in settled)
    month = Counter(r["date"][:7] for r in settled)
    mult = Counter(r["legs"] for r in bundles)
    summary = {
        "hypothesis_id": "FOOTBALL_PLUS1_5_MARKET_DOMINANCE_MULTI3_V1",
        "season": SEASON,
        "transport": "REQUIRED_COLUMNS_BY_HEADER_INDEX_EXTRA_TRAILING_FIELDS_ALLOWED",
        "usable_leagues": usable,
        "source_universe": LEAGUES,
        "pregame_event_rows": len(pregames),
        "eligible_events_pre_cap": sum(len(v) for v in by_date.values()),
        "selected_legs": n_leg,
        "leg_wins": w_leg,
        "leg_losses": n_leg - w_leg,
        "leg_rate": w_leg / n_leg if n_leg else 0.0,
        "leg_wilson95_lcb": leg_l,
        "leg_wilson95_ucb": leg_u,
        "candidate_dates": n_bundle,
        "bundle_wins": w_bundle,
        "bundle_losses": n_bundle - w_bundle,
        "bundle_rate": w_bundle / n_bundle if n_bundle else 0.0,
        "bundle_wilson95_lcb": bundle_l,
        "bundle_wilson95_ucb": bundle_u,
        "date_leg_count_distribution": dict(sorted(mult.items())),
        "max_legs_date": max(mult) if mult else 0,
        "max_team": team.most_common(1)[0] if team else None,
        "max_league": league.most_common(1)[0] if league else None,
        "max_month": month.most_common(1)[0] if month else None,
        "leg_gate_pass": n_leg >= MIN_N and leg_l >= MIN_LCB,
        "bundle_gate_pass": n_bundle >= MIN_N and bundle_l >= MIN_LCB,
        "source_gate_pass": usable >= MIN_SOURCE_LEAGUES,
        "duplicate_event_keys": duplicates,
        "decision": "SCIENCE_CERTAINTY_PASS" if (n_leg >= MIN_N and leg_l >= MIN_LCB and n_bundle >= MIN_N and bundle_l >= MIN_LCB) else "NO_PASS",
        "candidate_generation_used_outcomes": False,
    }
    (OUT / "source_audit.json").write_text(json.dumps(source, indent=2), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
