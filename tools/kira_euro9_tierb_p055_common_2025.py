from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

OUT = Path("artifacts/kira_euro9_tierb_p055_common_2025")
OUT.mkdir(parents=True, exist_ok=True)
START = date(2024, 12, 27)
END = date(2025, 12, 17)
LEAGUES = ["E0", "SP1", "D1", "I1", "F1", "N1", "P1", "SC0", "B1"]
SEASONS = ["2425", "2526"]
REQ = ["Date", "HomeTeam", "AwayTeam", "AvgCH", "AvgCD", "AvgCA"]
P_MIN = 0.55
MAX_PER_DATE = 3


def pdate(value: str):
    s = str(value or "").strip()
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
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    session = requests.Session()
    session.headers["User-Agent"] = "KIRA-EURO9-P055-COMMON25/1.0 outcome-blind"
    eligible: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for season in SEASONS:
        for league in LEAGUES:
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
            try:
                response = session.get(url, timeout=45)
                response.raise_for_status()
                raw = response.content
                encoding, rows = decode(raw)
            except Exception as exc:
                audit.append({
                    "season": season,
                    "league": league,
                    "status": "SOURCE_UNUSABLE",
                    "reason": type(exc).__name__,
                })
                continue

            sha = hashlib.sha256(raw).hexdigest()
            header = None
            header_idx = None
            for idx, row in enumerate(rows):
                cleaned = [str(x).strip() for x in row]
                if all(column in cleaned for column in REQ):
                    header = cleaned
                    header_idx = idx
                    break
            if header is None or header_idx is None:
                audit.append({
                    "season": season,
                    "league": league,
                    "status": "SOURCE_UNUSABLE",
                    "sha256": sha,
                    "reason": "MISSING_PREMATCH_COLUMNS",
                })
                continue

            index = {column: header.index(column) for column in REQ}
            max_idx = max(index.values())
            target_serial: list[str] = []
            valid_window_rows = 0
            eligible_rows = 0
            for row in rows[header_idx + 1:]:
                if len(row) <= max_idx:
                    continue
                game_date = pdate(row[index["Date"]])
                if game_date is None or game_date < START or game_date > END:
                    continue
                target_serial.append(",".join(row))
                home = row[index["HomeTeam"]].strip()
                away = row[index["AwayTeam"]].strip()
                try:
                    home_price = float(row[index["AvgCH"]])
                    draw_price = float(row[index["AvgCD"]])
                    away_price = float(row[index["AvgCA"]])
                except Exception:
                    continue
                if not home or not away or not all(math.isfinite(x) and x > 1.0 for x in (home_price, draw_price, away_price)):
                    continue
                valid_window_rows += 1
                qh, qd, qa = 1 / home_price, 1 / draw_price, 1 / away_price
                den = qh + qd + qa
                ph, pa = qh / den, qa / den
                if ph == pa:
                    continue
                side = "HOME" if ph > pa else "AWAY"
                probability = max(ph, pa)
                if probability < P_MIN:
                    continue
                key = (game_date.isoformat(), league, home, away)
                if key in seen:
                    continue
                seen.add(key)
                selected = home if side == "HOME" else away
                selected_price = home_price if side == "HOME" else away_price
                event_id = "EU9C-" + hashlib.sha256("|".join(key).encode()).hexdigest()[:20]
                eligible.append({
                    "date": game_date.isoformat(),
                    "season": season,
                    "league": league,
                    "Home": home,
                    "Away": away,
                    "selected_side": side,
                    "selected_entity": selected,
                    "selected_price": selected_price,
                    "p_favorite_novig": probability,
                    "event_id": event_id,
                })
                eligible_rows += 1

            audit.append({
                "season": season,
                "league": league,
                "status": "PASS",
                "sha256": sha,
                "encoding": encoding,
                "target_window_rows": len(target_serial),
                "target_window_rows_sha256": hashlib.sha256("\n".join(target_serial).encode()).hexdigest(),
                "valid_prematch_window_rows": valid_window_rows,
                "eligible_pre_cap": eligible_rows,
                "outcome_columns_requested": False,
            })

    if len(audit) != len(SEASONS) * len(LEAGUES) or any(row.get("status") != "PASS" for row in audit):
        summary = {"decision": "SOURCE_GATE_FAIL", "source_audit": audit}
        (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        by_date[row["date"]].append(row)

    selected: list[dict[str, Any]] = []
    for day, rows in sorted(by_date.items()):
        ranked = sorted(rows, key=lambda row: (
            -float(row["p_favorite_novig"]),
            float(row["selected_price"]),
            str(row["league"]),
            str(row["Home"]),
            str(row["Away"]),
            0 if row["selected_side"] == "HOME" else 1,
        ))[:MAX_PER_DATE]
        for rank, row in enumerate(ranked, 1):
            selected.append({**row, "date_rank": rank})

    write_csv(OUT / "euro9_p055_rows_common_2025.csv", selected)
    counts = Counter(row["date"] for row in selected)
    summary = {
        "hypothesis_id": "FOOTBALL_EURO9_FAVORITE_PLUS1_5_MULTI3_TIERB_P055_TRANSPORT_V1",
        "mode": "OUTCOME_BLIND_COMMON_WINDOW_RECONSTRUCTION",
        "window": [START.isoformat(), END.isoformat()],
        "calendar_days": (END - START).days + 1,
        "seasons": SEASONS,
        "leagues": LEAGUES,
        "p_min": P_MIN,
        "max_per_date": MAX_PER_DATE,
        "eligible_pre_cap": len(eligible),
        "selected_legs": len(selected),
        "candidate_dates": len(counts),
        "date_leg_count_distribution": dict(sorted(Counter(counts.values()).items())),
        "three_leg_dates": sum(value >= 3 for value in counts.values()),
        "outcomes_loaded": False,
        "outcome_columns_requested": False,
        "source_audit": audit,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
