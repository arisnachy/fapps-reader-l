from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

import gate0a_wnba_full_probe as base

OUT = Path("gate0a_artifacts")


def clean(v: Any) -> str:
    return base.clean(v)


def snapshot(page, event: dict[str, Any], phase: str) -> dict[str, Any]:
    selects = base.contextual_selects(page)
    rows = base.market_rows(page)[:5000]
    try:
        zone_text = clean(page.locator("#dvBetZone").inner_text(timeout=5000))[:60000]
    except Exception:
        zone_text = ""
    try:
        headers = page.locator("#dvBetZone .SchBZHeaderTitle,#dvBetZone .SchBZSubHeaderTitle,#dvBetZone [class*='HeaderTitle']").evaluate_all(
            "els=>els.map(e=>(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()).filter(Boolean)"
        )[:1000]
    except Exception:
        headers = []
    ttt_cells = []
    for row in rows:
        for cell in row.get("cells") or []:
            cid = clean(cell.get("id"))
            cls = clean(cell.get("class_name"))
            text = clean(cell.get("text"))
            if cid.startswith("TTT_") or "TTOU" in cls or "Team Total" in text:
                ttt_cells.append({
                    "id": cid,
                    "class_name": cls,
                    "text": text,
                    "actionable": bool(cell.get("actionable")),
                    "locked": bool(cell.get("locked")),
                    "row_participant": clean(row.get("participant_name")),
                    "section_title": clean(row.get("section_title")),
                })
    return {
        "phase": phase,
        "captured_at_utc": base.now_utc(),
        "event": event,
        "selects": selects,
        "team_total_selects": [s for s in selects if base.looks_team_total(s)],
        "team_total_cells": ttt_cells,
        "headers": headers,
        "dvBetZone_text": zone_text,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    network_events: dict[tuple[int, int], dict[str, Any]] = {}
    result = {
        "captured_at_utc": base.now_utc(),
        "mode": "READ_ONLY_WNBA_ADVANCED_PROPS_INVENTORY",
        "guards": [
            "No credentials/account state.",
            "No bet-selection cells are clicked.",
            "Only public navigation/market-section expansion is attempted.",
            "Failure to expose a submarket remains MARKET_DATA_PENDING, never market absence.",
        ],
        "events": [],
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 1800},
            locale="es-DO",
            timezone_id="America/Santo_Domingo",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        def on_response(resp):
            if not base.same_site(resp.url) or resp.request.resource_type not in {"xhr", "fetch"}:
                return
            try:
                body = resp.text()
                for event in base.extract_event_refs(body):
                    network_events[(event["header_id"], event["event_id"])] = event
            except Exception:
                return

        page.on("response", on_response)
        page.goto(base.START_URL, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(18000)
        clicked = base.click_exact_visible(page, "WNBA")
        result["wnba_header_clicked"] = clicked
        if clicked:
            page.wait_for_timeout(4000)
        events = base.discover_wnba_events(page, network_events) if clicked else []
        result["discovered_event_ids"] = [e["event_id"] for e in events]

        for event in events:
            ok, error = base.call_related(page, int(event["header_id"]), int(event["event_id"]))
            rec = {"event": event, "related_called": ok, "error": error, "phases": []}
            if not ok:
                result["events"].append(rec)
                continue
            page.wait_for_timeout(1000)
            rec["phases"].append(snapshot(page, event, "baseline"))

            # First try exact visible public section title. This is navigation only,
            # not a market/bet cell. If the title is not an actionable element, try
            # its nearest ancestor carrying onclick, but explicitly reject IDs/classes
            # that look like quote/bet cells.
            advanced_clicked = False
            loc = page.get_by_text("Advanced Player and Game Props", exact=True)
            for i in range(loc.count()):
                node = loc.nth(i)
                try:
                    if not node.is_visible():
                        continue
                    candidate = node.locator("xpath=ancestor-or-self::*[@onclick][1]")
                    target = candidate if candidate.count() else node
                    tid = clean(target.get_attribute("id"))
                    cls = clean(target.get_attribute("class"))
                    if tid.startswith(("PS_", "ML_", "TT_", "TTT_", "SZPS_", "SZTT_")) or "tooltip_addBet" in cls:
                        continue
                    target.scroll_into_view_if_needed(timeout=5000)
                    target.click(timeout=8000, force=True)
                    page.wait_for_timeout(2500)
                    advanced_clicked = True
                    break
                except Exception:
                    continue
            rec["advanced_props_clicked"] = advanced_clicked
            rec["phases"].append(snapshot(page, event, "after_advanced_props_click"))

            opened = base.expand_visible_more(page, limit=120)
            rec["more_expanders_opened_after_advanced"] = opened
            page.wait_for_timeout(1500)
            rec["phases"].append(snapshot(page, event, "after_more_expanders"))
            result["events"].append(rec)

        result["captured_at_utc_end"] = base.now_utc()
        browser.close()

    full = OUT / "WNBA_GATE0A_ADVANCED_PROPS.json"
    full.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "captured_at_utc": result["captured_at_utc"],
        "captured_at_utc_end": result.get("captured_at_utc_end"),
        "discovered_event_ids": result.get("discovered_event_ids"),
        "events": [
            {
                "event_id": rec["event"].get("event_id"),
                "title": rec["event"].get("title"),
                "advanced_props_clicked": rec.get("advanced_props_clicked"),
                "more_expanders_opened_after_advanced": rec.get("more_expanders_opened_after_advanced"),
                "phases": [
                    {
                        "phase": ph["phase"],
                        "select_count": len(ph.get("selects") or []),
                        "team_total_select_count": len(ph.get("team_total_selects") or []),
                        "team_total_cells": ph.get("team_total_cells"),
                        "headers": ph.get("headers"),
                        "zone_text_preview": clean(ph.get("dvBetZone_text"))[:4000],
                    }
                    for ph in rec.get("phases") or []
                ],
            }
            for rec in result.get("events") or []
        ],
        "decision": "DIAGNOSTIC_ONLY_MARKET_DATA_PENDING",
    }
    (OUT / "WNBA_GATE0A_ADVANCED_PROPS_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if clicked and events else 2


if __name__ == "__main__":
    raise SystemExit(main())
