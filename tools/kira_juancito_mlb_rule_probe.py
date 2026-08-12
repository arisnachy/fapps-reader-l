from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://www.juancitosport.com.do/deportes/"
OUT = Path("artifacts/kira_juancito_mlb_rule_probe")


def clean(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()


def safe_goto(page):
    err=""; status=None
    try:
        r=page.goto(PORTAL_URL,wait_until="commit",timeout=30000)
        status=r.status if r else None
    except PlaywrightTimeoutError as exc:
        err=f"{type(exc).__name__}: {exc}"
    page.wait_for_timeout(6000)
    return status,err


def surface(page):
    for f in page.frames:
        if "BOSSWagering/Sportsbook" in (f.url or ""):
            return f
    return page


def click_exact(s,label):
    loc=s.get_by_text(label,exact=True)
    for i in range(loc.count()):
        try:
            n=loc.nth(i)
            if n.is_visible():
                n.click(force=True,timeout=6000); s.page.wait_for_timeout(1500); return True
        except Exception: pass
    return False


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={"captured_at_utc":datetime.now(timezone.utc).isoformat(),"read_only":True}
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True)
        ctx=b.new_context(locale="es-DO",timezone_id="America/Santo_Domingo")
        page=ctx.new_page()
        requests=[]
        page.on("request",lambda r: requests.append({"url":r.url,"method":r.method,"resource_type":r.resource_type}) if re.search(r"rule|regla|book",r.url,re.I) else None)
        status,err=safe_goto(page)
        s=surface(page)
        result.update({"portal_http_status":status,"navigation_error":err,"surface_url":s.url})
        result["league_clicked"]=click_exact(s,"PROPUESTAS DE MLB")
        result["section_clicked"]=click_exact(s,"PROPUESTAS DE MLB - Total solo por equipo")
        page.wait_for_timeout(1200)
        result["header_outer_html"]=s.evaluate("() => {const e=document.getElementById('bzSHE_225'); return e ? e.outerHTML : ''}")
        result["header_descendants"]=s.evaluate(r"""
        () => { const root=document.getElementById('bzSHE_225'); if(!root)return [];
          const c=x=>(x||'').replace(/\s+/g,' ').trim();
          return Array.from(root.querySelectorAll('*')).map(e=>({tag:e.tagName,id:e.id||'',cls:e.className||'',title:e.getAttribute('title')||'',aria:e.getAttribute('aria-label')||'',onclick:e.getAttribute('onclick')||'',href:e.getAttribute('href')||'',text:c(e.innerText||e.textContent)})).slice(0,300);
        }
        """)
        result["global_rule_like_elements"]=s.evaluate(r"""
        () => { const c=x=>(x||'').replace(/\s+/g,' ').trim(); const rx=/(rule|regla|help|ayuda|info)/i;
          return Array.from(document.querySelectorAll('*')).filter(e=>rx.test([e.id,e.className,e.getAttribute('title'),e.getAttribute('aria-label'),e.getAttribute('onclick'),c(e.innerText||e.textContent)].join(' '))).map(e=>({tag:e.tagName,id:e.id||'',cls:e.className||'',title:e.getAttribute('title')||'',aria:e.getAttribute('aria-label')||'',onclick:e.getAttribute('onclick')||'',href:e.getAttribute('href')||'',text:c(e.innerText||e.textContent).slice(0,300)})).slice(0,500);
        }
        """)
        result["window_rule_keys"]=s.evaluate(r"""
        () => Object.keys(window).filter(k=>/(rule|regla|help)/i.test(k)).slice(0,300).map(k=>{let typ='';let src='';try{typ=typeof window[k]; if(typ==='function')src=String(window[k]).slice(0,1500)}catch(_){} return {key:k,type:typ,source:src};})
        """)
        result["script_rule_hits"]=s.evaluate(r"""
        () => Array.from(document.scripts).map((e,i)=>({i,src:e.src||'',text:(e.src?'':(e.textContent||'').slice(0,200000))})).filter(x=>/(rulebook|getrule|rules|regla)/i.test(x.src+' '+x.text)).slice(0,100).map(x=>({i:x.i,src:x.src,text_hits:(x.text.match(/.{0,120}(?:RuleBook|GetRule|Rules|Regla).{0,220}/ig)||[]).slice(0,20)}))
        """)
        result["rule_network_requests"]=requests
        b.close()
    (OUT/"rule_probe.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={
      "portal_http_status":result.get("portal_http_status"),"league_clicked":result.get("league_clicked"),"section_clicked":result.get("section_clicked"),
      "header_rule_like":sum(1 for e in result.get("header_descendants",[]) if re.search(r"rule|regla|help|info",json.dumps(e),re.I)),
      "global_rule_like_elements":len(result.get("global_rule_like_elements",[])),"window_rule_keys":len(result.get("window_rule_keys",[])),"script_rule_hits":len(result.get("script_rule_hits",[])),"rule_network_requests":len(result.get("rule_network_requests",[]))
    }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__": main()
