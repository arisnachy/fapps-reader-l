from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

import gate0a_wnba_full_probe as base

OUT = Path("gate0a_mlb_artifacts")
SOLO_MARKERS = ("solo", "team total", "total solo", "total equipo", "total de equipo")


def clean(v: Any) -> str:
    return base.clean(v)


def looks_solo_text(text: str) -> bool:
    t = clean(text).casefold()
    return any(marker in t for marker in SOLO_MARKERS)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    network_events: dict[tuple[int, int], dict[str, Any]] = {}
    result: dict[str, Any] = {
        "captured_at_utc": base.now_utc(),
        "mode": "READ_ONLY_MLB_SOLO_EXACT_CONTRACT_DISCOVERY",
        "guards": [
            "No credentials/account state.",
            "No wager/bet-selection controls are clicked.",
            "Only public MLB league/event/detail navigation and non-bet market-section expansion are used.",
            "This probe freezes only observed current product semantics; it does not score a sports strategy.",
            "Incomplete coverage remains MARKET_DATA_PENDING.",
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
        r = page.goto(base.START_URL, wait_until="domcontentloaded", timeout=120000)
        result["navigation"] = {"status": r.status if r else None, "url": base.redact_url(page.url)}
        page.wait_for_timeout(18000)

        clicked = base.click_exact_visible(page, "MLB")
        if not clicked:
            # Some Juancito builds expose the league as "USA - MLB" or under Baseball.
            clicked = base.click_exact_visible(page, "USA - MLB")
        result["mlb_header_clicked"] = clicked
        if clicked:
            page.wait_for_timeout(4000)

        # Restrict discovery to visible RelatedEvents links whose text/context says MLB
        # or whose network event is Baseball while MLB header has been opened.
        links = page.locator("a[onclick*='RelatedEvents']").evaluate_all(
            "els=>els.map(e=>({text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),onclick:e.getAttribute('onclick')||'',row:(e.closest('tr')?.innerText||'').replace(/\\s+/g,' ').trim()}))"
        ) if clicked else []
        import re
        events = {}
        for link in links:
            m = re.search(r"RelatedEvents\((\d+)\s*,\s*(\d+)", clean(link.get("onclick")))
            if not m:
                continue
            key = (int(m.group(1)), int(m.group(2)))
            evt = dict(network_events.get(key) or {})
            context_text = f"{clean(link.get('text'))} {clean(link.get('row'))} {clean(evt.get('sport'))}".casefold()
            if "mlb" not in context_text and clean(evt.get("sport")).casefold() != "baseball":
                continue
            evt.update({
                "header_id": key[0],
                "event_id": key[1],
                "title": clean(evt.get("title") or link.get("text")),
                "sport": evt.get("sport") or "Baseball",
                "league": "MLB",
            })
            events[key] = evt
        events = list(events.values())
        result["discovered_event_ids"] = [e["event_id"] for e in events]

        captured_ids = []
        for event in events:
            ok, error = base.call_related(page, int(event["header_id"]), int(event["event_id"]))
            rec: dict[str, Any] = {"event": event, "related_called": ok, "error": error, "captured_at_utc": base.now_utc()}
            if not ok:
                result["events"].append(rec)
                continue
            page.wait_for_timeout(800)
            opened = base.expand_visible_more(page, limit=120)
            page.wait_for_timeout(1200)
            rows = base.market_rows(page)[:6000]
            selects = base.contextual_selects(page)
            try:
                zone_text = clean(page.locator("#dvBetZone").inner_text(timeout=5000))[:80000]
            except Exception:
                zone_text = ""
            try:
                headers = page.locator("#dvBetZone .SchBZHeaderTitle,#dvBetZone .SchBZSubHeaderTitle,#dvBetZone [class*='HeaderTitle']").evaluate_all(
                    "els=>els.map(e=>(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()).filter(Boolean)"
                )[:1000]
            except Exception:
                headers = []

            solo_rows = []
            for row in rows:
                row_text = clean(row.get("text"))
                section = clean(row.get("section_title"))
                solo_cells = []
                for cell in row.get("cells") or []:
                    cid = clean(cell.get("id"))
                    cls = clean(cell.get("class_name"))
                    txt = clean(cell.get("text"))
                    # SOLO columns may not be text-labelled per participant. Preserve
                    # candidate cells when row/section/header context advertises SOLO,
                    # and keep exact IDs/classes/text/actionability for later binding.
                    if looks_solo_text(txt) or "solo" in cid.casefold() or "solo" in cls.casefold():
                        solo_cells.append(cell)
                if looks_solo_text(row_text) or looks_solo_text(section) or solo_cells:
                    solo_rows.append({
                        "section_title": section,
                        "participant_name": clean(row.get("participant_name")),
                        "text": row_text,
                        "cells": row.get("cells") or [],
                        "solo_cells": solo_cells,
                    })

            solo_selects = []
            for s in selects:
                hay = " ".join(clean(s.get(k)) for k in ("label", "title", "aria_label", "section_title", "context_text", "row_text"))
                if looks_solo_text(hay):
                    solo_selects.append(s)

            rec.update({
                "public_market_expanders_opened": opened,
                "headers": headers,
                "dvBetZone_text": zone_text,
                "solo_context_present": looks_solo_text(" ".join(headers) + " " + zone_text),
                "solo_rows": solo_rows,
                "solo_selects": solo_selects,
                "all_rows": rows,
            })
            captured_ids.append(event["event_id"])
            result["events"].append(rec)

        result["captured_event_ids"] = captured_ids
        result["missing_event_ids"] = sorted(set(result["discovered_event_ids"]) - set(captured_ids))
        result["coverage_complete"] = bool(clicked and events and set(captured_ids) == set(result["discovered_event_ids"]))
        result["captured_at_utc_end"] = base.now_utc()
        browser.close()

    (OUT / "MLB_GATE0A_SOLO_RAW.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "captured_at_utc": result.get("captured_at_utc"),
        "captured_at_utc_end": result.get("captured_at_utc_end"),
        "navigation": result.get("navigation"),
        "mlb_header_clicked": result.get("mlb_header_clicked"),
        "discovered_event_ids": result.get("discovered_event_ids"),
        "captured_event_ids": result.get("captured_event_ids"),
        "missing_event_ids": result.get("missing_event_ids"),
        "coverage_complete": result.get("coverage_complete"),
        "events": [
            {
                "event_id": e.get("event", {}).get("event_id"),
                "title": e.get("event", {}).get("title"),
                "headers": e.get("headers"),
                "solo_context_present": e.get("solo_context_present"),
                "solo_row_count": len(e.get("solo_rows") or []),
                "solo_select_count": len(e.get("solo_selects") or []),
                "solo_rows_preview": (e.get("solo_rows") or [])[:12],
                "zone_text_preview": clean(e.get("dvBetZone_text"))[:5000],
            }
            for e in result.get("events") or []
        ],
        "decision": "EXACT_CONTRACT_DISCOVERY_ONLY",
    }
    (OUT / "MLB_GATE0A_SOLO_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if clicked and events else 2


if __name__ == "__main__":
    raise SystemExit(main())
