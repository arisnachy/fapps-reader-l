from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

OUT = Path("artifacts/kira_euro9_tierb_p055_transport_v1")
OUT.mkdir(parents=True, exist_ok=True)
LEAGUES = ["E0", "SP1", "D1", "I1", "F1", "N1", "P1", "SC0", "B1"]
BLOCKS = [("DEV_2223", "2223"), ("OOS_2324", "2324")]
P_MIN = 0.55
MAX_PER_DATE = 3
MIN_LEGS = 300
MIN_DATES = 150
GATE = 0.90
REQ = ["Date", "HomeTeam", "AwayTeam", "AvgCH", "AvgCD", "AvgCA", "FTHG", "FTAG"]


def wilson(w: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = w / n
    den = 1 + z*z/n
    center = (p + z*z/(2*n))/den
    margin = z*math.sqrt((p*(1-p) + z*z/(4*n))/n)/den
    return max(0.0, center-margin), min(1.0, center+margin)


def pdate(v: str):
    s = str(v or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None


def decode(raw: bytes):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return enc, list(csv.reader(io.StringIO(raw.decode(enc), newline="")))
        except Exception:
            pass
    raise RuntimeError("CSV_DECODE_FAILED")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def fetch_season(season: str) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]], list[dict[str, Any]]]:
    session = requests.Session()
    session.headers["User-Agent"] = "KIRA-EURO9-TIERB-P055-TRANSPORT-V1/1.0"
    pre: list[dict[str, Any]] = []
    outcomes: dict[str, dict[str, int]] = {}
    audit: list[dict[str, Any]] = []
    all_sources_pass = True

    for league in LEAGUES:
        url = f"https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
        try:
            r = session.get(url, timeout=45)
            r.raise_for_status()
            raw = r.content
            enc, rows = decode(raw)
        except Exception as exc:
            audit.append({"league": league, "season": season, "status": "SOURCE_UNUSABLE", "reason": type(exc).__name__})
            all_sources_pass = False
            continue
        sha = hashlib.sha256(raw).hexdigest()
        header = None
        hi = None
        for i, row in enumerate(rows):
            h = [str(x).strip() for x in row]
            if all(c in h for c in REQ):
                header, hi = h, i
                break
        if header is None:
            audit.append({"league": league, "season": season, "status": "SOURCE_UNUSABLE", "sha256": sha, "reason": "MISSING_REQUIRED_COLUMNS"})
            all_sources_pass = False
            continue
        idx = {c: header.index(c) for c in REQ}
        mx = max(idx.values())
        valid = 0
        eligible = 0
        for rownum, row in enumerate(rows[hi+1:], hi+2):
            if len(row) <= mx:
                continue
            d = pdate(row[idx["Date"]])
            if d is None:
                continue
            home = row[idx["HomeTeam"]].strip()
            away = row[idx["AwayTeam"]].strip()
            try:
                h = float(row[idx["AvgCH"]]); dr = float(row[idx["AvgCD"]]); a = float(row[idx["AvgCA"]])
                hg = int(float(row[idx["FTHG"]])); ag = int(float(row[idx["FTAG"]]))
            except Exception:
                continue
            if not home or not away or not all(math.isfinite(x) and x > 1.0 for x in (h, dr, a)):
                continue
            valid += 1
            qh, qd, qa = 1/h, 1/dr, 1/a
            den = qh + qd + qa
            ph, pa = qh/den, qa/den
            if ph == pa:
                continue
            side = "HOME" if ph > pa else "AWAY"
            prob = max(ph, pa)
            if prob < P_MIN:
                continue
            selected = home if side == "HOME" else away
            price = h if side == "HOME" else a
            key_text = f"{season}|{league}|{d.isoformat()}|{home}|{away}"
            event_id = "EU9-" + hashlib.sha256(key_text.encode()).hexdigest()[:20]
            pre.append({
                "date": d.isoformat(), "season": season, "league": league,
                "Home": home, "Away": away, "selected_side": side,
                "selected_entity": selected, "selected_price": price,
                "p_favorite_novig": prob, "event_id": event_id,
            })
            outcomes[event_id] = {"home_goals": hg, "away_goals": ag}
            eligible += 1
        audit.append({
            "league": league, "season": season, "status": "PASS",
            "sha256": sha, "encoding": enc, "valid_rows": valid,
            "eligible_pre_cap": eligible,
            "required_columns": REQ,
        })

    if not all_sources_pass or len(audit) != len(LEAGUES):
        return [], {}, audit
    return pre, outcomes, audit


def select_cap(pre: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pre:
        by[row["date"]].append(row)
    selected: list[dict[str, Any]] = []
    for day, rows in sorted(by.items()):
        rows = sorted(rows, key=lambda r: (
            -float(r["p_favorite_novig"]), float(r["selected_price"]),
            str(r["league"]), str(r["Home"]), str(r["Away"]), str(r["selected_side"]),
        ))[:MAX_PER_DATE]
        for rank, row in enumerate(rows, 1):
            selected.append({**row, "date_rank": rank})
    return selected


def score(label: str, season: str) -> dict[str, Any]:
    block_dir = OUT / label.lower()
    block_dir.mkdir(parents=True, exist_ok=True)
    pre, outcomes, source_audit = fetch_season(season)
    source_pass = len(source_audit) == len(LEAGUES) and all(x.get("status") == "PASS" for x in source_audit)
    if not source_pass:
        summary = {"block": label, "season": season, "status": "SOURCE_GATE_FAIL", "source_audit": source_audit}
        (block_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        return summary

    selected = select_cap(pre)
    pre_path = block_dir / "selected_pre_settlement.csv"
    write_csv(pre_path, selected)
    pre_sha = hashlib.sha256(pre_path.read_bytes()).hexdigest()

    settled: list[dict[str, Any]] = []
    for row in selected:
        o = outcomes[row["event_id"]]
        gd = (o["home_goals"] - o["away_goals"]) if row["selected_side"] == "HOME" else (o["away_goals"] - o["home_goals"])
        hit = gd + 1.5 > 0
        settled.append({**row, **o, "selected_goal_diff": gd, "hit": hit})
    write_csv(block_dir / "settled_legs.csv", settled)
    write_csv(block_dir / "failures.csv", [r for r in settled if not r["hit"]])

    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in settled:
        by[row["date"]].append(row)
    bundles: list[dict[str, Any]] = []
    for day, rows in sorted(by.items()):
        bundles.append({
            "date": day, "legs": len(rows),
            "survived": all(bool(r["hit"]) for r in rows),
            "event_ids": "|".join(r["event_id"] for r in sorted(rows, key=lambda x: int(x["date_rank"]))),
        })
    write_csv(block_dir / "daily_bundles.csv", bundles)
    write_csv(block_dir / "bundle_failures.csv", [r for r in bundles if not r["survived"]])

    nl = len(settled); wl = sum(bool(r["hit"]) for r in settled)
    nd = len(bundles); wd = sum(bool(r["survived"]) for r in bundles)
    ll, lu = wilson(wl, nl); dl, du = wilson(wd, nd)
    lr = wl/nl if nl else 0.0; dr = wd/nd if nd else 0.0
    duplicate_events = nl - len({r["event_id"] for r in settled})
    distribution = Counter(int(r["legs"]) for r in bundles)
    gates = {
        "source_gate": source_pass,
        "legs_n_ge_300": nl >= MIN_LEGS,
        "dates_n_ge_150": nd >= MIN_DATES,
        "leg_rate_gt_90": lr > GATE,
        "leg_wilson_lcb_gt_90": ll > GATE,
        "bundle_rate_gt_90": dr > GATE,
        "bundle_wilson_lcb_gt_90": dl > GATE,
        "duplicate_event_keys_zero": duplicate_events == 0,
        "max3_per_date": all(int(r["legs"]) <= MAX_PER_DATE for r in bundles),
        "settlement_complete": len(outcomes) >= nl and len(settled) == nl,
        "candidate_generation_used_outcomes": False,
    }
    passed = all(gates.values())
    summary = {
        "hypothesis_id": "FOOTBALL_EURO9_FAVORITE_PLUS1_5_MULTI3_TIERB_P055_TRANSPORT_V1",
        "block": label, "season": season, "status": "PASS" if passed else "NO_PASS",
        "eligible_pre_cap": len(pre), "selected_legs": nl, "leg_wins": wl, "leg_losses": nl-wl,
        "leg_rate": lr, "leg_wilson95_lcb": ll, "leg_wilson95_ucb": lu,
        "candidate_dates": nd, "bundle_wins": wd, "bundle_losses": nd-wd,
        "bundle_rate": dr, "bundle_wilson95_lcb": dl, "bundle_wilson95_ucb": du,
        "date_leg_count_distribution": dict(sorted(distribution.items())),
        "selected_ledger_sha256": pre_sha, "duplicate_event_keys": duplicate_events,
        "gates": gates, "source_audit": source_audit,
        "frozen_contract": {"p_min": P_MIN, "line": "+1.5", "max_per_date": MAX_PER_DATE, "odds_columns": ["AvgCH","AvgCD","AvgCA"]},
    }
    (block_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    return summary


def main() -> int:
    overall: dict[str, Any] = {
        "hypothesis_id": "FOOTBALL_EURO9_FAVORITE_PLUS1_5_MULTI3_TIERB_P055_TRANSPORT_V1",
        "preregistration": "prereg/FOOTBALL_EURO9_FAVORITE_PLUS1_5_MULTI3_TIERB_P055_TRANSPORT_V1_2026-08-12.md",
        "blocks": [], "oos_opened": False,
    }
    dev = score(*BLOCKS[0])
    overall["blocks"].append(dev)
    if dev.get("status") != "PASS":
        overall["decision"] = "DEV_NO_PASS_TRANSPORT_CLOSED_OOS_UNOPENED"
        (OUT/"overall_summary.json").write_text(json.dumps(overall, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        print("KIRA_EURO9_TIERB", json.dumps(overall, ensure_ascii=False, sort_keys=True))
        return 0
    overall["oos_opened"] = True
    oos = score(*BLOCKS[1])
    overall["blocks"].append(oos)
    overall["decision"] = "OOS_TRANSPORT_PASS" if oos.get("status") == "PASS" else "OOS_NO_PASS_TRANSPORT_CLOSED"
    (OUT/"overall_summary.json").write_text(json.dumps(overall, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print("KIRA_EURO9_TIERB", json.dumps(overall, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
