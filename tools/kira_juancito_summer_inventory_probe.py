from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright

START_URL = "https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport"
OUT = Path("artifacts/kira_juancito_summer_inventory")
TARGETS = ("WNBA", "MLB", "PROPUESTAS DE MLB")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def redact_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        q = []
        for k, v in parse_qsl(parts.query, keep_blank_values=True):
            if k.casefold() in {"stoken", "session", "_session", "token", "customerid", "customerpin"}:
                v = "REDACTED"
            q.append((k, v))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))
    except Exception:
        return url


def same_site(url: str) -> bool:
    try:
        return (urlsplit(url).hostname or "").endswith("juancitosport.com.do")
    except Exception:
        return False


def extract_event_refs(body: str) -> list[dict]:
    out = []
    for match in re.finditer(r"newE\s*=\s*new Event\((.*?)\);\s*newHeader\.AddEvent", body or "", re.S):
        payload = match.group(1)
        head = re.match(r"\s*(-?\d+)\s*,\s*(\d+)\s*,", payload)
        if not head:
            continue
        title_match = re.match(r"\s*-?\d+\s*,\s*\d+\s*,\s*'((?:\\'|[^'])*)'", payload)
        title = title_match.group(1).replace("\\'", "'") if title_match else ""
        sport = ""
        for candidate in ("Basketball", "Baseball", "Tennis", "Soccer"):
            if f"'{candidate}'" in payload:
                sport = candidate
                break
        event_style = None
        # We intentionally do not guess positional EventStyle from the constructor.
        # Period evidence is collected separately from the rendered/event model.
        out.append({
            "header_id": int(head.group(1)),
            "event_id": int(head.group(2)),
            "title": title,
            "sport": sport,
            "event_style": event_style,
        })
    dedup = {(r["header_id"], r["event_id"]): r for r in out}
    return list(dedup.values())


def click_exact_visible(page, label: str) -> bool:
    loc = page.get_by_text(label, exact=True)
    for i in range(loc.count()):
        node = loc.nth(i)
        try:
            if node.is_visible():
                node.scroll_into_view_if_needed(timeout=3000)
                node.click(timeout=5000, force=True)
                page.wait_for_timeout(1600)
                return True
        except Exception:
            pass
    return False


def event_model_period(page, event_id: int) -> dict:
    # BOSS public pages expose EventStyle/IsEventNoFullTime in some rendered JS
    # models. Return evidence only if we can observe it explicitly.
    script = """
    (eid) => {
      const out = {event_id:eid, event_style:null, source:'', authoritative:false};
      const candidates = [];
      try {
        for (const k of Object.keys(window)) {
          const v = window[k];
          if (!v || typeof v !== 'object') continue;
          if (Array.isArray(v)) {
            for (const x of v) if (x && typeof x === 'object') candidates.push(x);
          }
        }
      } catch (_) {}
      for (const x of candidates) {
        const id = Number(x.EventID ?? x.eventID ?? x.EventId ?? x.eventId ?? x.ID ?? NaN);
        if (id !== Number(eid)) continue;
        const style = Number(x.EventStyle ?? x.eventStyle ?? NaN);
        if (Number.isFinite(style)) {
          out.event_style = style;
          out.source = 'window_event_object';
          out.authoritative = true;
          return out;
        }
      }
      return out;
    }
    """
    try:
        return page.evaluate(script, event_id)
    except Exception:
        return {"event_id": event_id, "event_style": None, "source": "", "authoritative": False}


def capture(page, label: str, event: dict | None = None) -> dict:
    rec = page.evaluate(
        """
        () => {
          const c = s => (s || '').replace(/\s+/g,' ').trim();
          const cells = Array.from(document.querySelectorAll('[id]')).filter(e => /^(SZ)?(ML|PS|TT)_\d+_/i.test(e.id || '')).map(e => ({
            id:e.id || '', text:c(e.innerText || e.textContent), cls:e.className || '', title:e.getAttribute('title') || '',
            aria:e.getAttribute('aria-label') || '', data:Object.fromEntries(Object.entries(e.dataset || {}).slice(0,20))
          })).slice(0,6000);
          const selects = Array.from(document.querySelectorAll('select')).map((e,i) => {
            const row=e.closest('tr');
            const container=e.closest('td,th,tr,div') || e.parentElement;
            return {index:i,id:e.id||'',name:e.name||'',aria:e.getAttribute('aria-label')||'',title:e.getAttribute('title')||'',
              row_text:c(row ? row.innerText || row.textContent : ''), context:c(container ? container.innerText || container.textContent : '').slice(0,1600),
              options:Array.from(e.options||[]).slice(0,80).map(o=>({text:c(o.textContent),value:o.value,selected:o.selected,disabled:o.disabled}))};
          });
          const links=Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e=>({text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''})).slice(0,1000);
          const body=c(document.body ? document.body.innerText : '').slice(0,120000);
          return {body, cells, selects, related_links:links};
        }
        """
    )
    # Public surface only; remove potentially session-shaped strings if the page echoed any.
    body = rec.get("body", "")
    body = re.sub(r"(?i)(stoken|session|token|customerpin)\s*[=:]\s*[^\s&]+", r"\1=REDACTED", body)
    rec["body"] = body
    rec.update({"label": label, "captured_at_utc": now_utc(), "url": redact_url(page.url)})
    if event:
        rec["event"] = event
        rec["period_model"] = event_model_period(page, int(event["event_id"]))
    return rec


def call_related(page, header_id: int, event_id: int) -> tuple[bool, str]:
    try:
        ok = page.evaluate("typeof RelatedEvents === 'function'")
        if not ok:
            return False, "RelatedEvents_not_available"
        page.evaluate("([h,e]) => RelatedEvents(h,e,1,0)", [header_id, event_id])
        page.wait_for_timeout(1800)
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    network_events: dict[tuple[int,int],dict] = {}
    results = {"captured_at_utc": now_utc(), "targets": {}, "guards": [
        "anonymous public read-only only", "no bet/coupon/account controls clicked", "no credentials/session persisted",
        "period is UNKNOWN unless explicit authoritative EventStyle/model evidence is observed"
    ]}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="es-DO", timezone_id="America/Santo_Domingo", viewport={"width":1440,"height":1200})
        page = context.new_page()

        def on_response(resp):
            if not same_site(resp.url) or resp.request.resource_type not in {"xhr", "fetch"}:
                return
            try:
                text = resp.text()
            except Exception:
                return
            for ev in extract_event_refs(text):
                network_events[(ev["header_id"], ev["event_id"])] = ev

        page.on("response", on_response)
        response = page.goto(START_URL, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(3500)
        results["navigation_status"] = response.status if response else None
        results["base"] = capture(page, "base")

        for target in TARGETS:
            clicked = click_exact_visible(page, target)
            target_rec = {"clicked": clicked, "event_details": []}
            target_rec["board"] = capture(page, target)
            refs = {}
            for link in target_rec["board"].get("related_links", []):
                m = re.search(r"RelatedEvents\((\d+)\s*,\s*(\d+)", link.get("onclick", ""))
                if m:
                    key = (int(m.group(1)), int(m.group(2)))
                    ev = dict(network_events.get(key) or {})
                    ev.update({"header_id":key[0],"event_id":key[1],"visible_text":clean(link.get("text"))})
                    refs[key] = ev
            # If link text is sparse, retain only events observed while this target board was active
            # that match the expected sport; cap detail calls for safety/time.
            expected = "Basketball" if target == "WNBA" else "Baseball"
            for key, ev in network_events.items():
                if ev.get("sport") == expected:
                    refs.setdefault(key, ev)
            for n, ev in enumerate(list(refs.values())[:40], 1):
                ok, err = call_related(page, int(ev["header_id"]), int(ev["event_id"]))
                detail = {"event": ev, "called": ok, "error": err}
                if ok:
                    detail["snapshot"] = capture(page, f"{target}_{n:02d}_{ev['event_id']}", ev)
                target_rec["event_details"].append(detail)
            results["targets"][target] = target_rec
            # Return to root before next target to avoid context drift.
            page.goto(START_URL, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(1800)
        browser.close()

    # Derive compact hints only from captured public text/options/cells; no market promotion here.
    hints = []
    markers = ("solo", "team total", "total equipo", "total del equipo", "total por equipo", "run line", "super run")
    for target, tr in results["targets"].items():
        for detail in tr.get("event_details", []):
            snap = detail.get("snapshot") or {}
            eid = (detail.get("event") or {}).get("event_id")
            for sel in snap.get("selects", []):
                text = " | ".join([clean(sel.get("row_text")), clean(sel.get("context")), " ".join(clean(o.get("text")) for o in sel.get("options", []))])
                if any(m in text.casefold() for m in markers):
                    hints.append({"target":target,"event_id":eid,"kind":"select","text":text[:2000],"period_model":snap.get("period_model")})
            for cell in snap.get("cells", []):
                text = " | ".join([clean(cell.get("id")), clean(cell.get("text")), clean(cell.get("title")), clean(cell.get("aria"))])
                if any(m in text.casefold() for m in markers):
                    hints.append({"target":target,"event_id":eid,"kind":"cell","text":text[:1000],"period_model":snap.get("period_model")})
    results["summer_market_hints"] = hints[:1000]
    (OUT / "summer_inventory.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps({
        "captured_at_utc": results["captured_at_utc"],
        "navigation_status": results.get("navigation_status"),
        "target_counts": {k:{"clicked":v.get("clicked"),"details":len(v.get("event_details",[]))} for k,v in results["targets"].items()},
        "summer_market_hint_count": len(results["summer_market_hints"]),
        "period_guard": "UNKNOWN unless authoritative explicit model evidence",
    }, indent=2), encoding="utf-8")
    print((OUT / "summary.json").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
