from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://www.juancitosport.com.do/deportes/"
OUT = Path("artifacts/kira_juancito_wnba_team_total_network_v2")
SENSITIVE = re.compile(r"customer|account|token|session|cookie|password|authorization|balance|cuenta", re.I)
TT_RX = re.compile(r"team\s*total|total.*equipo|equipo.*total|playerprops|player.*props", re.I)


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def safe_path(url: str) -> str:
    try:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}{parts.path}"
    except Exception:
        return ""


def surface(page):
    for frame in page.frames:
        if "BOSSWagering/Sportsbook" in (frame.url or ""):
            return frame
    return page


def goto(page):
    status = None
    error = ""
    try:
        response = page.goto(PORTAL_URL, wait_until="commit", timeout=30000)
        status = response.status if response else None
    except PlaywrightTimeoutError as exc:
        error = f"{type(exc).__name__}: {exc}"
    page.wait_for_timeout(6000)
    return status, error


def click_wnba(s):
    loc = s.get_by_text("WNBA", exact=True)
    for idx in range(loc.count()):
        item = loc.nth(idx)
        try:
            if item.is_visible():
                item.scroll_into_view_if_needed(timeout=3000)
                item.click(force=True, timeout=6000)
                return True
        except Exception:
            continue
    return False


def related_refs(s):
    rows = s.evaluate(r"""
    () => Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e => ({
      text:(e.innerText||e.textContent||'').replace(/\s+/g,' ').trim(),
      onclick:e.getAttribute('onclick')||''
    }))
    """)
    found = {}
    for row in rows:
        match = re.search(r"RelatedEvents\((\d+)\s*,\s*(\d+)", row.get("onclick", ""))
        if match:
            found[(int(match.group(1)), int(match.group(2)))] = {
                "header_id": int(match.group(1)),
                "event_id": int(match.group(2)),
                "text": clean(row.get("text")),
            }
    return list(found.values())


def call_related(s, header_id: int, event_id: int):
    if not s.evaluate("typeof RelatedEvents === 'function'"):
        return False, "RelatedEvents_missing"
    try:
        s.evaluate("([h,e]) => RelatedEvents(h,e,1,0)", [header_id, event_id])
        s.page.wait_for_timeout(1800)
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def structural_capture(s):
    return s.evaluate(r"""
    () => {
      const c = x => (x||'').replace(/\s+/g,' ').trim();
      const attrs = e => Object.fromEntries(Array.from(e.attributes||[]).map(a => [a.name,a.value]).slice(0,60));
      const all = Array.from(document.querySelectorAll('*'));
      const tt = all.filter(e => /team\s*total|total.*equipo|equipo.*total|advanced player and game props/i.test(c(e.innerText||e.textContent)) && c(e.innerText||e.textContent).length < 600);
      return {
        body:c(document.body?document.body.innerText:'').slice(0,80000),
        playerprops:Array.from(document.querySelectorAll('#Playerprops')).map(e => ({
          tag:e.tagName,id:e.id||'',class:e.className||'',attrs:attrs(e),
          text:c(e.innerText||e.textContent),html:(e.outerHTML||'').slice(0,50000),
          parent_html:(e.parentElement?.outerHTML||'').slice(0,90000)
        })),
        tt_elements:tt.slice(0,200).map(e => ({
          tag:e.tagName,id:e.id||'',class:e.className||'',attrs:attrs(e),
          text:c(e.innerText||e.textContent),
          parent_tag:e.parentElement?.tagName||'',parent_id:e.parentElement?.id||'',parent_class:e.parentElement?.className||'',
          parent_text:c(e.parentElement?.innerText||e.parentElement?.textContent||''),
          parent_html:(e.parentElement?.outerHTML||'').slice(0,50000),
          row_html:(e.closest('tr')?.outerHTML||'').slice(0,50000)
        })),
        id_cells:Array.from(document.querySelectorAll('[id]')).filter(e => {
          const id=e.id||''; const t=c(e.innerText||e.textContent); const cls=String(e.className||'');
          return /team|total|prop/i.test(id+' '+cls+' '+t) && t.length<1000;
        }).slice(0,800).map(e => ({tag:e.tagName,id:e.id||'',class:e.className||'',attrs:attrs(e),text:c(e.innerText||e.textContent),html:(e.outerHTML||'').slice(0,12000)}))
      };
    }
    """)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "account_data_used": False,
        "wager_actions_performed": False,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="es-DO", timezone_id="America/Santo_Domingo", viewport={"width": 1440, "height": 1400})
        page = ctx.new_page()
        network: list[dict] = []
        response_candidates: list[dict] = []

        def on_request(request):
            if request.resource_type not in {"xhr", "fetch", "document", "script"}:
                return
            post = request.post_data or ""
            post_safe = "[REDACTED_SENSITIVE_POST]" if SENSITIVE.search(post) else post[:4000]
            network.append({
                "phase": "request",
                "method": request.method,
                "resource_type": request.resource_type,
                "url_path": safe_path(request.url),
                "post_data": post_safe,
            })

        def on_response(response):
            request = response.request
            if request.resource_type not in {"xhr", "fetch"}:
                return
            rec = {
                "phase": "response",
                "status": response.status,
                "resource_type": request.resource_type,
                "url_path": safe_path(response.url),
            }
            network.append(rec)
            try:
                body = response.text()
            except Exception:
                return
            if SENSITIVE.search(body):
                # Never persist response bodies that look account/session related.
                return
            if TT_RX.search(body) or re.search(r"\b(4[5-9]|5\d|6[0-5])(?:\.5)?\b", body):
                response_candidates.append({**rec, "body": body[:180000]})

        page.on("request", on_request)
        page.on("response", on_response)
        status, nav_error = goto(page)
        s = surface(page)
        result.update({"portal_http_status": status, "navigation_error": nav_error, "surface_url_path": safe_path(s.url)})
        result["wnba_clicked"] = click_wnba(s)
        page.wait_for_timeout(1800)
        refs = related_refs(s)
        result["refs"] = refs
        details = []

        for ref in refs[:12]:
            ok, err = call_related(s, ref["header_id"], ref["event_id"])
            rec = {"ref": ref, "related_called": ok, "error": err}
            if not ok:
                details.append(rec)
                continue
            rec["before"] = structural_capture(s)
            start_network = len(network)
            start_candidates = len(response_candidates)

            parent = s.locator("#Playerprops")
            clicked = False
            click_error = ""
            try:
                for idx in range(parent.count()):
                    node = parent.nth(idx)
                    if node.is_visible():
                        node.scroll_into_view_if_needed(timeout=3000)
                        node.click(force=True, timeout=7000)
                        clicked = True
                        break
            except Exception as exc:
                click_error = f"{type(exc).__name__}: {exc}"
            rec["playerprops_parent_clicked"] = clicked
            rec["playerprops_click_error"] = click_error
            page.wait_for_timeout(4000)
            rec["after"] = structural_capture(s)
            rec["network_delta"] = network[start_network:]
            rec["response_candidates_delta"] = response_candidates[start_candidates:]
            details.append(rec)

        result["details"] = details
        result["network_event_count"] = len(network)
        result["candidate_response_count"] = len(response_candidates)
        browser.close()

    # Extract purely public numeric candidates from structural/network evidence.
    text = json.dumps(result, ensure_ascii=False)
    protective = sorted(set(float(x) for x in re.findall(r"(?<!\d)(\d{2}(?:\.5)?)(?!\d)", text) if 45 <= float(x) <= 65))
    result["protective_numeric_candidates_45_65"] = protective
    result["decision"] = "PROTECTIVE_NUMERIC_EVIDENCE_PRESENT_REQUIRES_BINDING" if protective else "NO_PROTECTIVE_TT_LINE_OBSERVED_V2"

    (OUT / "wnba_team_total_network_v2.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "portal_http_status": result.get("portal_http_status"),
        "wnba_clicked": result.get("wnba_clicked"),
        "event_refs": len(result.get("refs") or []),
        "parent_clicks": sum(bool(x.get("playerprops_parent_clicked")) for x in details),
        "network_event_count": result.get("network_event_count"),
        "candidate_response_count": result.get("candidate_response_count"),
        "protective_numeric_candidates_45_65": protective,
        "decision": result["decision"],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
