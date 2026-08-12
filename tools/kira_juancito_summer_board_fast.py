from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://www.juancitosport.com.do/deportes/"
OUT = Path("artifacts/kira_juancito_summer_board_fast")
TARGETS = ("WNBA", "MLB", "PROPUESTAS DE MLB")


def clean(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()


def safe_goto(page, url):
    status = None
    error = ""
    try:
        response = page.goto(url, wait_until="commit", timeout=30000)
        status = response.status if response else None
    except PlaywrightTimeoutError as exc:
        error = f"{type(exc).__name__}: {exc}"
    page.wait_for_timeout(6000)
    return status, error


def sportsbook_surface(page):
    # Prefer the embedded BOSS frame. We never copy cookies/storage or inspect account state.
    frames = []
    for frame in page.frames:
        frames.append(frame.url)
        if "BOSSWagering/Sportsbook" in (frame.url or ""):
            return frame, frames
    # Some layouts navigate the page itself to BOSS.
    if "BOSSWagering/Sportsbook" in (page.url or ""):
        return page, frames
    return page, frames


def click_exact(surface, label):
    loc = surface.get_by_text(label, exact=True)
    for i in range(loc.count()):
        try:
            n = loc.nth(i)
            if n.is_visible():
                n.click(timeout=5000, force=True)
                surface.page.wait_for_timeout(1800) if hasattr(surface, "page") else None
                return True
        except Exception:
            pass
    return False


def capture(surface):
    return surface.evaluate(r"""
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
        status,error=safe_goto(page,PORTAL_URL)
        surface,frames=sportsbook_surface(page)
        result["http_status"]=status
        result["navigation_error"]=error
        result["portal_url"]=page.url
        result["frames"]=frames
        result["sportsbook_surface_url"]=getattr(surface,"url","")
        for target in TARGETS:
            clicked=click_exact(surface,target)
            page.wait_for_timeout(1800)
            snap=capture(surface)
            body=snap.get("body","")
            snap["body"]=re.sub(r"(?i)(stoken|session|token|customerpin)\s*[=:]\s*[^\s&]+",r"\1=REDACTED",body)
            result["targets"][target]={"clicked":clicked,**snap}
            # Do not reload the sportsbook between target tabs; keep the same public anonymous surface.
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
    print(json.dumps({"http_status":result.get("http_status"),"portal_url":result.get("portal_url"),"sportsbook_surface_url":result.get("sportsbook_surface_url"),"frames":len(result.get("frames",[])),"targets":summary,"hint_count":len(result["hints"]),"navigation_error":result.get("navigation_error")},indent=2))


if __name__ == "__main__":
    main()
