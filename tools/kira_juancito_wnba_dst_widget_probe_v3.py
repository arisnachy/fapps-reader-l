from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://www.juancitosport.com.do/deportes/"
OUT = Path("artifacts/kira_juancito_wnba_dst_widget_v3")
CURRENCIES = ["DOP", "USD"]


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def safe_path(url: str) -> str:
    try:
        p = urlsplit(url)
        return f"{p.scheme}://{p.netloc}{p.path}"
    except Exception:
        return ""


def surface(page):
    for frame in page.frames:
        if "BOSSWagering/Sportsbook" in (frame.url or ""):
            return frame
    return page


def click_wnba(s):
    loc = s.get_by_text("WNBA", exact=True)
    for idx in range(loc.count()):
        node = loc.nth(idx)
        try:
            if node.is_visible():
                node.click(force=True, timeout=6000)
                return True
        except Exception:
            continue
    return False


def first_event(s):
    rows = s.evaluate(r"""
    () => Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e => ({
      text:(e.innerText||e.textContent||'').replace(/\s+/g,' ').trim(), onclick:e.getAttribute('onclick')||''
    }))
    """)
    for row in rows:
        m = re.search(r"RelatedEvents\((\d+)\s*,\s*(\d+)", row.get("onclick", ""))
        if m:
            return int(m.group(1)), int(m.group(2)), clean(row.get("text"))
    return None


def with_currency(src: str, currency: str) -> str:
    p = urlsplit(src)
    query = dict(parse_qsl(p.query, keep_blank_values=True))
    query["currency"] = currency
    # token is retained only in-memory for the vendor's public embedded widget request.
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(query), p.fragment))


def capture_widget(page, url: str, currency: str) -> dict:
    rec = {"currency": currency, "url_path": safe_path(url), "status": None, "navigation_error": ""}
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
        rec["status"] = response.status if response else None
    except PlaywrightTimeoutError as exc:
        rec["navigation_error"] = f"{type(exc).__name__}: {exc}"
    page.wait_for_timeout(5000)
    try:
        body = clean(page.locator("body").inner_text(timeout=10000))
    except Exception:
        body = ""
    rec["body"] = body[:180000]
    rec["body_len"] = len(body)
    try:
        rec["structured"] = page.evaluate(r"""
        () => {
          const c=x=>(x||'').replace(/\s+/g,' ').trim();
          const attrs=e=>Object.fromEntries(Array.from(e.attributes||[]).map(a=>[a.name,a.value]).filter(([k,v])=>!/token|auth|session|cookie/i.test(k+' '+v)).slice(0,40));
          return Array.from(document.querySelectorAll('body *')).filter(e=>{
            const t=c(e.innerText||e.textContent); const id=e.id||''; const cls=String(e.className||'');
            return t.length>0 && t.length<1200 && (/team\s*total|total.*team|total.*equipo|equipo.*total/i.test(t) || /team|total|market|prop/i.test(id+' '+cls));
          }).slice(0,1200).map(e=>({tag:e.tagName,id:e.id||'',class:String(e.className||''),attrs:attrs(e),text:c(e.innerText||e.textContent)}));
        }
        """)
    except Exception:
        rec["structured"] = []
    # Numeric values only count as candidates when their nearby text is market-like.
    candidates = []
    for item in rec["structured"]:
        text = clean(item.get("text"))
        if re.search(r"team\s*total|total.*team|total.*equipo|equipo.*total", text, re.I):
            vals = sorted(set(float(x) for x in re.findall(r"(?<!\d)(\d{2}(?:\.5)?)(?!\d)", text) if 20 <= float(x) <= 120))
            if vals:
                candidates.append({"text": text[:2500], "values_20_120": vals})
    rec["team_total_candidates"] = candidates
    rec["protective_45_65"] = sorted(set(v for row in candidates for v in row["values_20_120"] if 45 <= v <= 65))
    return rec


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "wager_actions_performed": False,
        "account_login_used": False,
        "embedded_token_persisted": False,
        "currency_candidates": CURRENCIES,
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="es-DO", timezone_id="America/Santo_Domingo", viewport={"width":1440,"height":1200})
        portal = ctx.new_page()
        try:
            response = portal.goto(PORTAL_URL, wait_until="commit", timeout=30000)
            result["portal_status"] = response.status if response else None
        except Exception as exc:
            result["portal_status"] = None
            result["portal_error"] = f"{type(exc).__name__}: {exc}"
        portal.wait_for_timeout(6000)
        s = surface(portal)
        result["wnba_clicked"] = click_wnba(s)
        portal.wait_for_timeout(1600)
        event = first_event(s)
        result["first_event"] = {"header_id":event[0],"event_id":event[1],"text":event[2]} if event else None
        if event and s.evaluate("typeof RelatedEvents === 'function'"):
            s.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[event[0],event[1]])
            portal.wait_for_timeout(2000)
        src = ""
        try:
            src = s.locator("#iframeDSTProps").first.get_attribute("src") or ""
        except Exception:
            pass
        result["widget_found"] = bool(src)
        result["widget_url_path"] = safe_path(src) if src else ""
        result["widget_query_keys"] = sorted(k for k,_ in parse_qsl(urlsplit(src).query, keep_blank_values=True) if not re.search(r"token|user", k, re.I)) if src else []
        probes = []
        if src:
            for currency in CURRENCIES:
                page = ctx.new_page()
                probes.append(capture_widget(page, with_currency(src, currency), currency))
                page.close()
        result["probes"] = probes
        browser.close()

    protective = sorted(set(v for rec in result["probes"] for v in rec.get("protective_45_65", [])))
    any_team_total = any(rec.get("team_total_candidates") for rec in result["probes"])
    result["protective_45_65"] = protective
    result["decision"] = (
        "EXACT_PROTECTIVE_TEAM_TOTAL_CANDIDATE_OBSERVED_REQUIRES_OPERATOR_BINDING" if protective
        else "TEAM_TOTAL_WIDGET_DATA_OBSERVED_NONPROTECTIVE" if any_team_total
        else "DST_WIDGET_NO_TEAM_TOTAL_DATA"
    )
    (OUT / "wnba_dst_widget_v3.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "portal_status": result.get("portal_status"),
        "wnba_clicked": result.get("wnba_clicked"),
        "widget_found": result.get("widget_found"),
        "widget_url_path": result.get("widget_url_path"),
        "currencies_probed": CURRENCIES,
        "probe_statuses": [{"currency":x["currency"],"status":x.get("status"),"body_len":x.get("body_len"),"protective":x.get("protective_45_65")} for x in probes],
        "protective_45_65": protective,
        "decision": result["decision"],
        "embedded_token_persisted": False,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
