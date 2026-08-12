from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://www.juancitosport.com.do/deportes/"
OUT = Path("artifacts/kira_juancito_mlb_rla")
LEAGUE_LABEL = "PROPUESTAS DE MLB"
SECTION_LABEL = "PROPUESTAS DE MLB - Run Line Alternativo"


def clean(v): return re.sub(r"\s+", " ", str(v or "")).strip()

def safe_goto(page):
    err=""; status=None
    try:
        r=page.goto(PORTAL_URL,wait_until="commit",timeout=30000); status=r.status if r else None
    except PlaywrightTimeoutError as exc: err=f"{type(exc).__name__}: {exc}"
    page.wait_for_timeout(6000); return status,err

def surface(page):
    for f in page.frames:
        if "BOSSWagering/Sportsbook" in (f.url or ""): return f
    return page

def click_exact(s,label):
    loc=s.get_by_text(label,exact=True); attempts=[]
    for i in range(loc.count()):
        n=loc.nth(i); meta={"index":i}
        try:
            meta.update(n.evaluate("e=>({tag:e.tagName,id:e.id||'',cls:e.className||'',onclick:e.getAttribute('onclick')||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()})"))
            meta["visible"]=n.is_visible()
            if meta["visible"]:
                n.click(force=True,timeout=6000); attempts.append({**meta,"clicked":True}); return True,attempts
        except Exception as exc: meta["error"]=f"{type(exc).__name__}: {exc}"
        attempts.append(meta)
    return False,attempts

def capture(s):
    return s.evaluate(r"""
    () => { const c=x=>(x||'').replace(/\s+/g,' ').trim(); return {
      body:c(document.body?document.body.innerText:'').slice(0,150000),
      cells:Array.from(document.querySelectorAll('[id]')).filter(e=>/^(SZ)?PS_\d+_/i.test(e.id||'')).map(e=>({id:e.id||'',text:c(e.innerText||e.textContent),title:e.getAttribute('title')||'',aria:e.getAttribute('aria-label')||'',row_text:c(e.closest('tr')?e.closest('tr').innerText||e.closest('tr').textContent:'')})).slice(0,8000),
      related:Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e=>({text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''})).slice(0,1500)
    }}
    """)

def parse(snapshot):
    rows=[]
    for cell in snapshot.get('cells',[]):
        text=clean(cell.get('text')); cid=str(cell.get('id') or '')
        if not text: continue
        m=re.search(r'([+-]\d+(?:\.5)?)\s+([+-]\d{3,4}|Even)',text,re.I)
        idm=re.match(r'^(?:SZ)?PS_(\d+)_([123])$',cid,re.I)
        rows.append({'cell_id':cid,'cell_event_id':int(idm.group(1)) if idm else None,'selection_code':int(idm.group(2)) if idm else None,'text':text,'line':float(m.group(1)) if m else None,'american_price':m.group(2) if m else None,'row_text':clean(cell.get('row_text'))})
    return rows

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'read_only':True,'section_label':SECTION_LABEL,'science_status':'NOT_PREREGISTERED_DO_NOT_SCORE'}
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True); ctx=b.new_context(locale='es-DO',timezone_id='America/Santo_Domingo',viewport={'width':1440,'height':1300}); page=ctx.new_page()
        status,err=safe_goto(page); s=surface(page); result.update({'portal_http_status':status,'navigation_error':err,'surface_url':s.url})
        result['league_clicked'],result['league_attempts']=click_exact(s,LEAGUE_LABEL); page.wait_for_timeout(1000)
        result['section_clicked'],result['section_attempts']=click_exact(s,SECTION_LABEL); page.wait_for_timeout(2200)
        snap=capture(s); result['snapshot']=snap; result['parsed_rla_rows']=parse(snap); b.close()
    counts={}
    for r in result['parsed_rla_rows']:
        if r['line'] is not None: counts[str(r['line'])]=counts.get(str(r['line']),0)+1
    result['decision']='CURRENT_RLA_ROWS_CAPTURED' if result['section_clicked'] and result['parsed_rla_rows'] else 'RLA_DETAIL_ROWS_PENDING'
    (OUT/'rla.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'portal_http_status':result.get('portal_http_status'),'league_clicked':result.get('league_clicked'),'section_clicked':result.get('section_clicked'),'rla_rows':len(result['parsed_rla_rows']),'line_counts':counts,'related_links':len(snap.get('related',[])),'decision':result['decision']}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8'); print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
