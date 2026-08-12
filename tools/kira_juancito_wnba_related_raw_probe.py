from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://www.juancitosport.com.do/deportes/"
OUT = Path("artifacts/kira_juancito_wnba_related_raw")


def clean(v): return re.sub(r"\s+", " ", str(v or "")).strip()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"captured_at_utc": datetime.now(timezone.utc).isoformat(), "read_only": True, "science_status": "MARKET_DISCOVERY_ONLY"}
    responses = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="es-DO", timezone_id="America/Santo_Domingo", viewport={"width":1440,"height":1400})
        page = ctx.new_page()
        def on_response(resp):
            try:
                if "GetRelatedEvents" not in resp.url and "BOSSWagering" not in resp.url: return
                ct=(resp.headers.get("content-type") or "").lower()
                if not any(x in ct for x in ("text","json","javascript","html")): return
                txt=resp.text()
                if "GetRelatedEvents" in resp.url or "new Event(" in txt or "Team Total" in txt:
                    responses.append({"url":resp.url,"status":resp.status,"content_type":ct,"body":txt[:2_000_000]})
            except Exception: pass
        page.on("response", on_response)
        status=None; nav_error=""
        try:
            r=page.goto(PORTAL_URL,wait_until="commit",timeout=30000); status=r.status if r else None
        except PlaywrightTimeoutError as exc: nav_error=f"{type(exc).__name__}: {exc}"
        page.wait_for_timeout(6000)
        s=next((f for f in page.frames if "BOSSWagering/Sportsbook" in (f.url or "")), page)
        out.update({"portal_http_status":status,"navigation_error":nav_error,"surface_url":s.url})
        loc=s.get_by_text("WNBA",exact=True); clicked=False
        for i in range(loc.count()):
            try:
                n=loc.nth(i)
                if n.is_visible(): n.click(force=True,timeout=6000); clicked=True; break
            except Exception: pass
        out["wnba_clicked"]=clicked; page.wait_for_timeout(1600)
        refs=s.evaluate(r"""
        () => { const c=x=>(x||'').replace(/\s+/g,' ').trim(); return Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(a=>({text:c(a.innerText||a.textContent),onclick:a.getAttribute('onclick')||''})); }
        """)
        uniq=[]; seen=set()
        for x in refs:
            m=re.search(r"RelatedEvents\((\d+)\s*,\s*(\d+)",x.get("onclick", ""))
            if m:
                key=(int(m.group(1)),int(m.group(2)))
                if key not in seen: seen.add(key); uniq.append({"header_id":key[0],"event_id":key[1],"text":clean(x.get("text"))})
        out["refs"]=uniq
        probes=[]
        for ref in uniq[:20]:
            try:
                s.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[ref["header_id"],ref["event_id"]]); page.wait_for_timeout(1000)
                body=clean(s.evaluate("document.body ? document.body.innerText : ''"))
                probes.append({"ref":ref,"called":True,"body":body[:120000]})
            except Exception as exc: probes.append({"ref":ref,"called":False,"error":f"{type(exc).__name__}: {exc}"})
        out["probes"]=probes
        browser.close()
    out["responses"]=responses

    constructors=[]
    for r in responses:
        for m in re.finditer(r"newE\s*=\s*new Event\((.*?)\);", r.get("body", ""), re.S):
            raw=m.group(1)
            title=""
            mt=re.match(r"\s*([^,]+),\s*([^,]+),\s*'([^']*)'",raw)
            if mt: title=mt.group(3)
            constructors.append({"url":r.get("url"),"title":title,"raw":"new Event("+raw+")"})
    out["event_constructors"]=constructors
    team_total=[x for x in constructors if re.search(r"team total|total.*team|total.*equipo|equipo.*total",x.get("title",""),re.I)]
    # Also retain all proposition-looking constructors for review because Juancito may use numeric/template labels instead of literal Team Total text.
    proposition=[]
    for x in constructors:
        raw=x.get("raw","")
        if re.search(r",\s*50\s*,\s*\d+\s*,\s*'[^']*'\s*,",raw): proposition.append(x)
    out["team_total_constructors"]=team_total
    out["proposition_constructors"]=proposition
    summary={
        "portal_http_status":out.get("portal_http_status"),"wnba_clicked":out.get("wnba_clicked"),"related_refs":len(uniq),
        "network_responses":len(responses),"event_constructors":len(constructors),"team_total_constructors":len(team_total),
        "proposition_constructors":len(proposition),"team_total_titles":sorted(set(x.get("title") for x in team_total)),
        "decision":"CURRENT_WNBA_TEAM_TOTAL_CHILD_EVENT_FOUND" if team_total else "TEAM_TOTAL_CHILD_EVENT_NOT_LITERAL_IN_RELATED_RAW"
    }
    out["summary"]=summary
    (OUT/"related_raw.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
