from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

import gate0a_wnba_full_probe as base

OUT = Path("gate0a_artifacts")


def clean(v: Any) -> str:
    return base.clean(v)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    network_events: dict[tuple[int, int], dict[str, Any]] = {}
    result: dict[str, Any] = {
        "captured_at_utc": base.now_utc(),
        "mode": "READ_ONLY_WNBA_FULL_SURFACE_DIAGNOSTIC",
        "events": [],
        "guards": [
            "No credentials/account state.",
            "No bet-selection control clicks.",
            "This diagnostic cannot emit C2 market absence or PASS.",
        ],
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
        try:
            r = page.goto(base.START_URL, wait_until="domcontentloaded", timeout=120_000)
            result["navigation"] = {"status": r.status if r else None, "url": base.redact_url(page.url)}
        except PlaywrightTimeoutError as exc:
            result["navigation"] = {"error": f"{type(exc).__name__}: {exc}", "url": base.redact_url(page.url)}
        page.wait_for_timeout(18_000)
        clicked = base.click_exact_visible(page, "WNBA")
        result["wnba_header_clicked"] = clicked
        if clicked:
            page.wait_for_timeout(4_000)
        events = base.discover_wnba_events(page, network_events) if clicked else []
        result["discovered_event_ids"] = [e["event_id"] for e in events]

        for event in events:
            ok, error = base.call_related(page, int(event["header_id"]), int(event["event_id"]))
            rec: dict[str, Any] = {**event, "related_called": ok, "error": error, "captured_at_utc": base.now_utc()}
            if not ok:
                result["events"].append(rec)
                continue
            opened = base.expand_visible_more(page, limit=80)
            page.wait_for_timeout(1200)
            selects = base.contextual_selects(page)
            rows = base.market_rows(page)[:4000]
            try:
                zone_text = clean(page.locator("#dvBetZone").inner_text(timeout=5_000))[:40000]
            except Exception:
                zone_text = ""
            try:
                headers = page.locator("#dvBetZone .SchBZHeaderTitle,#dvBetZone .SchBZSubHeaderTitle,#dvBetZone [class*='HeaderTitle']").evaluate_all(
                    "els=>els.map(e=>(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()).filter(Boolean)"
                )[:500]
            except Exception:
                headers = []
            rec.update({
                "public_market_expanders_opened": opened,
                "all_selects": selects,
                "market_rows": rows,
                "headers": headers,
                "dvBetZone_text": zone_text,
                "team_total_candidate_count": sum(1 for s in selects if base.looks_team_total(s)),
            })
            result["events"].append(rec)
        result["captured_at_utc_end"] = base.now_utc()
        browser.close()

    path = OUT / "WNBA_GATE0A_SURFACE_DIAG.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compact = {
        "captured_at_utc": result.get("captured_at_utc"),
        "captured_at_utc_end": result.get("captured_at_utc_end"),
        "navigation": result.get("navigation"),
        "wnba_header_clicked": result.get("wnba_header_clicked"),
        "discovered_event_ids": result.get("discovered_event_ids"),
        "events": [
            {
                "event_id": e.get("event_id"),
                "title": e.get("title"),
                "related_called": e.get("related_called"),
                "select_count": len(e.get("all_selects") or []),
                "team_total_candidate_count": e.get("team_total_candidate_count"),
                "market_row_count": len(e.get("market_rows") or []),
                "headers": e.get("headers"),
                "zone_text_preview": clean(e.get("dvBetZone_text"))[:2500],
            }
            for e in result.get("events") or []
        ],
        "decision": "DIAGNOSTIC_ONLY_MARKET_DATA_PENDING",
    }
    (OUT / "WNBA_GATE0A_SURFACE_DIAG_SUMMARY.json").write_text(json.dumps(compact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(compact, ensure_ascii=False))
    return 0 if clicked and events else 2


if __name__ == "__main__":
    raise SystemExit(main())
