from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

START_URL = (
    "https://deportes.juancitosport.com.do/"
    "BOSSWagering/Sportsbook/InternetBetTaker/"
    "?lng=es-ES&siteid=jssport"
)
OUT = Path("gate0a_artifacts")
TARGET_LINES = {54.5, 55.5, 56.5, 57.5}
TEAM_TOTAL_MARKERS = (
    "team total", "team_total", "teamtotal", "total equipo", "total de equipo",
    "total del equipo", "total por equipo", "total solo por equipo",
)
SOURCE_MANIFEST = {
    "source_repo": "arisnachy/pelota",
    "source_branch": "kira/public-market-green",
    "transport_kind": "runner-independent anonymous read-only replica",
    "reference_modules": [
        "tools/juancito_deep_market_probe.py",
        "tools/juancito_structured_market_probe.py",
        "tools/juancito_wnba_team_total_full_probe.py",
    ],
    "guards": [
        "No credentials or account state are read.",
        "No bet-selection control is clicked.",
        "Only public league/event/detail navigation and Team Total dropdown option changes are performed.",
        "Incomplete coverage never proves market absence.",
    ],
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def redact_text(text: str) -> str:
    text = str(text or "")
    text = re.sub(r"(?i)(stoken|_session|session|token)=([^&'\"\\\s]+)", r"\1=REDACTED", text)
    text = re.sub(r"(?i)(SessionID\s*[=:]\s*['\"])[^'\"]+", r"\1REDACTED", text)
    text = re.sub(r"(?i)(PlayerInfo\s*[=:]\s*['\"])[A-Za-z0-9+/=_-]{20,}", r"\1REDACTED", text)
    return text


def redact_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        query = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key.lower() in {"stoken", "_session", "session", "token"}:
                value = "REDACTED"
            query.append((key, value))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    except Exception:
        return url


def same_site(url: str) -> bool:
    try:
        return (urlsplit(url).hostname or "").endswith("juancitosport.com.do")
    except Exception:
        return False


def numeric_line(value: Any) -> float | None:
    m = re.search(r"(?<!\d)([-+]?\d+(?:[\.,]\d+)?)(?!\d)", clean(value))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def extract_event_refs(body: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for match in re.finditer(r"newE\s*=\s*new Event\((.*?)\);\s*newHeader\.AddEvent", body or "", re.S):
        payload = match.group(1)
        head = re.match(r"\s*(-?\d+)\s*,\s*(\d+)\s*,", payload)
        if not head:
            continue
        title_match = re.match(r"\s*-?\d+\s*,\s*\d+\s*,\s*'((?:\\'|[^'])*)'", payload)
        title = title_match.group(1).replace("\\'", "'") if title_match else ""
        sport = None
        for candidate in ("Basketball", "Tennis", "Soccer", "Baseball"):
            if f"'{candidate}'" in payload:
                sport = candidate
                break
        out.append({
            "header_id": int(head.group(1)),
            "event_id": int(head.group(2)),
            "sport": sport,
            "title": title,
        })
    dedup = {(x["header_id"], x["event_id"]): x for x in out}
    return list(dedup.values())


def click_exact_visible(page, label: str) -> bool:
    loc = page.get_by_text(label, exact=True)
    for i in range(loc.count()):
        try:
            node = loc.nth(i)
            if node.is_visible():
                node.scroll_into_view_if_needed(timeout=5_000)
                node.click(timeout=8_000, force=True)
                return True
        except Exception:
            continue
    return False


def call_related(page, header_id: int, event_id: int) -> tuple[bool, str | None]:
    try:
        if not page.evaluate("typeof RelatedEvents === 'function'"):
            return False, "RelatedEvents_not_available"
        page.evaluate("([h,e]) => { RelatedEvents(h,e,1,0); }", [header_id, event_id])
        page.wait_for_timeout(4_000)
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def expand_visible_more(page, limit: int = 40) -> int:
    selector = "#dvBetZone a, #dvBetZone button, #dvBetZone [onclick]"
    opened = 0
    for i in range(min(page.locator(selector).count(), 1400)):
        node = page.locator(selector).nth(i)
        try:
            text = clean(node.inner_text(timeout=400)).casefold()
            title = clean(node.get_attribute("title")).casefold()
            if text not in {"más", "mas", "more"} and title not in {"más", "mas", "more"}:
                continue
            if not node.is_visible():
                continue
            node.click(timeout=3_000, force=True)
            page.wait_for_timeout(500)
            opened += 1
            if opened >= limit:
                break
        except Exception:
            continue
    return opened


def contextual_selects(page) -> list[dict[str, Any]]:
    return page.locator("select").evaluate_all(
        """
        els => {
          const clean = s => (s || '').replace(/\s+/g, ' ').trim();
          const section = el => {
            let node = el;
            while (node && node !== document.body) {
              let prev = node.previousElementSibling;
              while (prev) {
                if (prev.matches && prev.matches('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]')) {
                  const t = clean(prev.innerText || prev.textContent); if (t) return t;
                }
                if (prev.querySelectorAll) {
                  const hs = prev.querySelectorAll('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]');
                  if (hs.length) { const t = clean(hs[hs.length-1].innerText || hs[hs.length-1].textContent); if (t) return t; }
                }
                prev = prev.previousElementSibling;
              }
              node = node.parentElement;
            }
            return '';
          };
          return els.map((e,i) => {
            const row = e.closest('tr');
            const participant = row ? row.querySelector('.colParticipantInfoParticipant,.SchUpcomingParticipant,.upcomingParticipantName') : null;
            let label='';
            if (e.id) { const lab=document.querySelector(`label[for="${CSS.escape(e.id)}"]`); if(lab) label=clean(lab.innerText||lab.textContent); }
            if (!label) { const lab=e.closest('label'); if(lab) label=clean(lab.innerText||lab.textContent); }
            const rowText=row ? clean(row.innerText||row.textContent) : '';
            const container=e.closest('td,th,tr,table,div') || e.parentElement;
            return {
              index:i,id:e.id||'',name:e.name||'',value:e.value||'',label,
              aria_label:e.getAttribute('aria-label')||'',title:e.getAttribute('title')||'',
              section_title:section(e),
              participant_name:participant ? clean(participant.innerText||participant.textContent) : '',
              row_text:rowText,
              context_text:clean([section(e),label,rowText,container?clean(container.innerText||container.textContent):''].filter(Boolean).join(' | ')).slice(0,3000),
              options:Array.from(e.options||[]).map(o=>({text:clean(o.textContent),value:o.value,selected:o.selected,disabled:o.disabled}))
            };
          });
        }
        """
    )


def market_rows(page) -> list[dict[str, Any]]:
    if page.locator("#dvBetZone").count() == 0:
        return []
    rows = page.locator("#dvBetZone tr").evaluate_all(
        """
        rows => {
          const clean=s=>(s||'').replace(/\s+/g,' ').trim();
          const section=el=>{
            let node=el;
            while(node && node.id!=='dvBetZone' && node!==document.body){
              let prev=node.previousElementSibling;
              while(prev){
                if(prev.matches && prev.matches('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]')){const t=clean(prev.innerText||prev.textContent);if(t)return t;}
                if(prev.querySelectorAll){const hs=prev.querySelectorAll('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]');if(hs.length){const t=clean(hs[hs.length-1].innerText||hs[hs.length-1].textContent);if(t)return t;}}
                prev=prev.previousElementSibling;
              }
              node=node.parentElement;
            }
            return '';
          };
          return rows.map((r,index)=>{
            const p=r.querySelector('.colParticipantInfoParticipant,.SchUpcomingParticipant,.upcomingParticipantName');
            const participant_name=p?clean(p.innerText||p.textContent):'';
            const cells=Array.from(r.querySelectorAll(':scope > th,:scope > td')).map(c=>({text:clean(c.innerText||c.textContent),id:c.id||'',class_name:typeof c.className==='string'?c.className:'',actionable:c.classList?c.classList.contains('tooltip_addBet'):false,locked:c.classList?c.classList.contains('cellCandado'):false}));
            const actions=Array.from(r.querySelectorAll('a,button,[onclick],.tooltip_addBet')).map(a=>({tag_name:(a.tagName||'').toLowerCase(),text:clean(a.innerText||a.textContent),id:a.id||'',class_name:typeof a.className==='string'?a.className:'',title:a.getAttribute('title')||'',aria_label:a.getAttribute('aria-label')||'',onclick:a.getAttribute('onclick')||'',row_text:clean(r.innerText||r.textContent),participant_name,actionable:a.classList?a.classList.contains('tooltip_addBet'):false,locked:a.classList?a.classList.contains('cellCandado'):false,data:Object.fromEntries(Array.from(a.attributes||[]).filter(x=>x.name.startsWith('data-')).map(x=>[x.name,x.value]))}));
            return {index,section_title:section(r),participant_name,text:clean(r.innerText||r.textContent),cells,actions};
          }).filter(x=>x.text||x.cells.length||x.actions.length);
        }
        """
    )
    for row in rows:
        for action in row.get("actions") or []:
            action["onclick"] = redact_text(action.get("onclick"))
            action["data"] = {str(k): redact_text(str(v)) for k, v in (action.get("data") or {}).items()}
    return rows


def looks_team_total(select: dict[str, Any]) -> bool:
    haystack = " ".join(clean(select.get(k)).casefold() for k in ("id","name","label","aria_label","title","section_title","context_text"))
    if any(marker in haystack for marker in TEAM_TOTAL_MARKERS):
        return True
    return "total puntos" in haystack and bool(clean(select.get("participant_name")))


def discover_wnba_events(page, network_events: dict[tuple[int,int],dict[str,Any]]) -> list[dict[str,Any]]:
    links = page.locator("a[onclick*='RelatedEvents']").evaluate_all("els=>els.map(e=>({text:(e.innerText||e.textContent||'').trim(),onclick:e.getAttribute('onclick')||''}))")
    events: dict[tuple[int,int],dict[str,Any]] = {}
    for link in links:
        m = re.search(r"RelatedEvents\((\d+)\s*,\s*(\d+)", clean(link.get("onclick")))
        if not m:
            continue
        key=(int(m.group(1)),int(m.group(2)))
        event=dict(network_events.get(key) or {})
        event.update({"header_id":key[0],"event_id":key[1],"title":clean(event.get("title") or link.get("text")),"sport":event.get("sport") or "Basketball","league":"WNBA"})
        events[key]=event
    return list(events.values())


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest={**SOURCE_MANIFEST,"captured_at_utc":now_utc(),"navigation":{},"wnba_header_clicked":False,"discovered_event_ids":[],"captured_event_ids":[],"missing_event_ids":[],"coverage_complete":False,"events":[]}
    network_events: dict[tuple[int,int],dict[str,Any]]={}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(viewport={"width":1440,"height":1400},locale="es-DO",timezone_id="America/Santo_Domingo",user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36")
        page=context.new_page()
        def on_response(resp):
            if not same_site(resp.url) or resp.request.resource_type not in {"xhr","fetch"}: return
            try:
                for event in extract_event_refs(resp.text()): network_events[(event["header_id"],event["event_id"])]=event
            except Exception: return
        page.on("response",on_response)
        try:
            r=page.goto(START_URL,wait_until="domcontentloaded",timeout=120_000)
            manifest["navigation"]={"status":r.status if r else None,"url":redact_url(page.url)}
        except PlaywrightTimeoutError as exc:
            manifest["navigation"]={"error":f"{type(exc).__name__}: {exc}","url":redact_url(page.url)}
        page.wait_for_timeout(18_000)
        clicked=click_exact_visible(page,"WNBA")
        manifest["wnba_header_clicked"]=clicked
        if clicked: page.wait_for_timeout(4_000)
        events=discover_wnba_events(page,network_events) if clicked else []
        manifest["discovered_event_ids"]=[e["event_id"] for e in events]
        captured=[]
        for event_no,event in enumerate(events,1):
            ok,error=call_related(page,event["header_id"],event["event_id"])
            rec={**event,"related_called":ok,"error":error,"captured_at_utc":now_utc(),"team_total_selects":[]}
            if not ok:
                manifest["events"].append(rec); continue
            expand_visible_more(page)
            page.wait_for_timeout(800)
            selects=contextual_selects(page)
            candidates=[s for s in selects if looks_team_total(s)]
            for select in candidates:
                selrec={"select_index":select["index"],"participant_name":clean(select.get("participant_name")),"section_title":clean(select.get("section_title")),"context_text":clean(select.get("context_text"))[:1500],"options":[],"baseline_rows":market_rows(page)[:2500]}
                for option in (select.get("options") or [])[:50]:
                    if option.get("disabled"): continue
                    line=numeric_line(option.get("text") or option.get("value"))
                    if line is None: continue
                    obs={"line":line,"option_text":clean(option.get("text")),"option_value":clean(option.get("value")),"target_c2_line":line in TARGET_LINES,"captured_at_utc":now_utc()}
                    try:
                        locator=page.locator("select").nth(int(select["index"]))
                        if clean(option.get("value")): locator.select_option(value=clean(option.get("value")),timeout=5_000)
                        else: locator.select_option(label=clean(option.get("text")),timeout=5_000)
                        page.wait_for_timeout(900)
                        obs["status"]="CAPTURED"
                        obs["captured_at_utc"]=now_utc()
                        obs["market_rows"]=market_rows(page)[:2500]
                    except Exception as exc:
                        obs["status"]="SELECT_OPTION_FAILED"; obs["error"]=f"{type(exc).__name__}: {exc}"
                    selrec["options"].append(obs)
                rec["team_total_selects"].append(selrec)
            captured.append(event["event_id"])
            manifest["events"].append(rec)
        manifest["captured_event_ids"]=captured
        discovered=set(manifest["discovered_event_ids"]); cap=set(captured)
        manifest["missing_event_ids"]=sorted(discovered-cap)
        manifest["coverage_complete"]=bool(clicked and discovered and discovered==cap)
        manifest["captured_at_utc_end"]=now_utc()
        browser.close()
    (OUT/"WNBA_GATE0A_FULL_RAW.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary={
        "captured_at_utc":manifest.get("captured_at_utc"),"captured_at_utc_end":manifest.get("captured_at_utc_end"),"navigation":manifest.get("navigation"),"wnba_header_clicked":manifest.get("wnba_header_clicked"),"discovered_event_ids":manifest.get("discovered_event_ids"),"captured_event_ids":manifest.get("captured_event_ids"),"missing_event_ids":manifest.get("missing_event_ids"),"coverage_complete":manifest.get("coverage_complete"),
        "events":[{"event_id":e.get("event_id"),"title":e.get("title"),"related_called":e.get("related_called"),"error":e.get("error"),"team_total_selects":[{"select_index":s.get("select_index"),"participant_name":s.get("participant_name"),"section_title":s.get("section_title"),"lines":[o.get("line") for o in s.get("options") or []],"target_lines":[o.get("line") for o in s.get("options") or [] if o.get("target_c2_line")]} for s in e.get("team_total_selects") or []]} for e in manifest.get("events") or []],
        "decision_guard":"This raw anonymous capture alone cannot emit C2 PASS. TEAM-3 must exact-bind event/team/market/period/Over/target line/price/state/freshness and settlement. C2 incompatibility requires coverage_complete=true plus complete Team Total ladders with no target line."
    }
    (OUT/"WNBA_GATE0A_COVERAGE_SUMMARY.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))
    return 0 if manifest.get("wnba_header_clicked") else 2

if __name__=="__main__": raise SystemExit(main())
