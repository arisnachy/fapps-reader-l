from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

OUT = Path("artifacts/kira_mlb_statsapi_source_audit")
BASE = "https://statsapi.mlb.com/api/v1/schedule"
SEASONS = [2012, 2013]


def audit_season(session: requests.Session, season: int) -> dict:
    params = {"sportId": 1, "season": season, "gameType": "R"}
    response = session.get(BASE, params=params, timeout=90)
    response.raise_for_status()
    raw = response.content
    payload = response.json()

    dates = payload.get("dates") or []
    game_pks = []
    game_dates = []
    status_codes = {}
    duplicate_count = 0
    seen = set()
    schema_keys = set()

    for date_row in dates:
        if date_row.get("date"):
            game_dates.append(str(date_row["date"]))
        for game in date_row.get("games") or []:
            schema_keys.update(game.keys())
            pk = game.get("gamePk")
            if pk is not None:
                if pk in seen:
                    duplicate_count += 1
                seen.add(pk)
                game_pks.append(int(pk))
            code = str(((game.get("status") or {}).get("statusCode")) or "")
            status_codes[code] = status_codes.get(code, 0) + 1
            # SCIENCE FIREWALL: do not access teams.*.score, linescore or winner fields.

    return {
        "season": season,
        "endpoint": BASE,
        "query": params,
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "copyright_present": bool(payload.get("copyright")),
        "top_level_keys": sorted(payload.keys()),
        "game_schema_keys_observed": sorted(schema_keys),
        "schedule_date_rows": len(dates),
        "game_count": len(game_pks),
        "unique_game_pks": len(seen),
        "duplicate_game_pk_count": duplicate_count,
        "first_schedule_date": min(game_dates) if game_dates else None,
        "last_schedule_date": max(game_dates) if game_dates else None,
        "status_code_counts": status_codes,
        "individual_scores_read_or_emitted": False,
        "outcome_settlement_computed": False,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "KIRA-source-identity-audit/1.0"})
    audits = [audit_season(session, season) for season in SEASONS]
    result = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_host": "statsapi.mlb.com",
        "sport_id": 1,
        "game_type": "R",
        "science_firewall": {
            "2012_role": "DEV_RESERVED",
            "2013_role": "OOS_SEALED_UNSCORED",
            "individual_scores_read_or_emitted": False,
            "candidate_settlement_computed": False,
        },
        "seasons": audits,
    }
    (OUT / "source_audit.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    # stdout intentionally excludes any individual game/team/outcome rows.
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
