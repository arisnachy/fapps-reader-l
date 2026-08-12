from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

START_URL = "https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport"
OUT = Path("artifacts/kira_juancito_summer_board_fast")
TARGETS = ("WNBA", "MLB", "PROPUESTAS DE MLB")


def clean(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()


def click_exact(page, label):
    loc = page.get_by_text(label, exact=True)
    for i in range(loc.count()):
        try:
            n = loc.nth(i)
            if n.is_visible():
                n.click(timeout=5000, force=True)
                page.wait_for_timeout(1800)
                return True
        except Exception:
            pass
    return False


def capture(page):
    return page.evaluate("""
    () => {
      const c=s=>(s||'').replace(/\s+/g,' ').trim();
      return {
        body:c(document.body ? document.body.innerText : '').slice(0,90000),
        boss_cells:Array.from(document.querySelectorAll('[id]')).filter(e=>/^(SZ)?(ML|PS|TT)_\d+_/i.test(e.id||'')).map(e=>({id:e.id,text:c(e.innerText||e.textContent),title:e.getAttribute('title')||'',aria:e.getAttribute('aria-label')||''})).slice(0,4000),
        selects:Array.from(document.querySelectorAll('select')).map((e,i)=>({index:i,id:e.id||'',name:e.name||'',text:c(e.closest('tr') ? e.closest('tr').innerText : e.parentElement ? e.parentElement.innerText : ''),options:Array.from(e.options||[]).map(o=>c(o.textContent)).slice(0,80)})).slice(0,300),
        related:Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e=>({text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''})).slice(0,500)
      };
    }
    """)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result={"captured_at_utc":datetime.now(timezone.utc).isoformat(),"targets":{},"read_only":True}
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True)
        ctx=b.new_context(locale="es-DO", timezone_id="America/Santo_Domingo")
        page=ctx.new_page()
        resp=page.goto(START_URL, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(2500)
        result["http_status"]=resp.status if resp else None
        for target in TARGETS:
            clicked=click_exact(page,target)
            snap=capture(page)
            body=snap.get("body","")
            # Public text only; redact obvious token-shaped query echoes.
            snap["body"]=re.sub(r"(?i)(stoken|session|token|customerpin)\s*[=:]\s*[^\s&]+",r"\1=REDACTED",body)
            result["targets"][target]={"clicked":clicked,**snap}
            page.goto(START_URL, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(800)
        b.close()
    hints=[]
    keywords=("solo", "team total", "total equipo", "total del equipo", "total por equipo", "super run", "run line alternativo")
    for target,snap in result["targets"].items():
        for line in snap.get("body","").split(" | "):
            if any(k in line.casefold() for k in keywords):
                hints.append({"target":target,"text":line[:1200]})
        for sel in snap.get("selects",[]):
            text=" | ".join([clean(sel.get("text"))," / ".join(sel.get("options",[]))])
            if any(k in text.casefold() for k in keywords):
                hints.append({"target":target,"kind":"select","text":text[:1800]})
    result["hints"]=hints[:500]
    (OUT/"board.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={k:{"clicked":v["clicked"],"cells":len(v.get("boss_cells",[])),"selects":len(v.get("selects",[])),"related":len(v.get("related",[]))} for k,v in result["targets"].items()}
    print(json.dumps({"http_status":result.get("http_status"),"targets":summary,"hint_count":len(result["hints"])},indent=2))


if __name__ == "__main__":
    main()
