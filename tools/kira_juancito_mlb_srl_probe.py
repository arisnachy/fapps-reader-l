from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://www.juancitosport.com.do/deportes/"
OUT = Path("artifacts/kira_juancito_mlb_srl")
LEAGUE_LABEL = "PROPUESTAS DE MLB"
SECTION_LABEL = "PROPUESTAS DE MLB - Super Run Line"


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


def sportsbook_frame(page):
    for f in page.frames:
        if "BOSSWagering/Sportsbook" in (f.url or ""):
            return f
    return page


def click_exact(surface,label):
    loc=surface.get_by_text(label,exact=True)
    attempts=[]
    for i in range(loc.count()):
        n=loc.nth(i); meta={"index":i}
        try:
            meta.update(n.evaluate("e=>({tag:e.tagName,id:e.id||'',cls:e.className||'',onclick:e.getAttribute('onclick')||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()})"))
            meta["visible"]=n.is_visible()
            if meta["visible"]:
                n.scroll_into_view_if_needed(timeout=3000)
                n.click(force=True,timeout=6000)
                attempts.append({**meta,"clicked":True})
                return True,attempts
        except Exception as exc:
            meta["error"]=f"{type(exc).__name__}: {exc}"
        attempts.append(meta)
    return False,attempts


def capture(surface):
    return surface.evaluate(r"""
    () => {
      const c=s=>(s||'').replace(/\s+/g,' ').trim();
      return {
        body:c(document.body?document.body.innerText:'').slice(0,150000),
        cells:Array.from(document.querySelectorAll('[id]')).filter(e=>/^(SZ)?(ML|PS|TT)_\d+_/i.test(e.id||'')).map(e=>({
          id:e.id||'',text:c(e.innerText||e.textContent),title:e.getAttribute('title')||'',aria:e.getAttribute('aria-label')||'',cls:e.className||'',
          row_text:c(e.closest('tr') ? e.closest('tr').innerText || e.closest('tr').textContent : '')
        })).slice(0,8000),
        related:Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e=>({text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''})).slice(0,1500),
        rows:Array.from(document.querySelectorAll('tr')).map((e,i)=>({index:i,id:e.id||'',cls:e.className||'',text:c(e.innerText||e.textContent)})).filter(x=>x.text).slice(0,4000)
      };
    }
    """)


def parse_srl(snapshot):
    parsed=[]
    for cell in snapshot.get('cells',[]):
        cid=str(cell.get('id') or '')
        if not re.match(r'^(?:SZ)?PS_',cid,re.I):
            continue
        text=clean(cell.get('text'))
        if not text:
            continue
        # Example expected: +2.5 -145 or -3.5 +115
        m=re.search(r'([+-]\d+(?:\.5)?)\s+([+-]\d{3,4}|Even)',text,re.I)
        line=float(m.group(1)) if m else None
        price=m.group(2) if m else None
        row=clean(cell.get('row_text'))
        idm=re.match(r'^(?:SZ)?PS_(\d+)_([123])$',cid,re.I)
        parsed.append({
          'cell_id':cid,'cell_event_id':int(idm.group(1)) if idm else None,'selection_code':int(idm.group(2)) if idm else None,
          'text':text,'line':line,'american_price':price,'row_text':row
        })
    return parsed


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={"captured_at_utc":datetime.now(timezone.utc).isoformat(),"read_only":True,"section_label":SECTION_LABEL,"science_status":"NOT_PREREGISTERED_DO_NOT_SCORE"}
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True)
        ctx=b.new_context(locale='es-DO',timezone_id='America/Santo_Domingo',viewport={'width':1440,'height':1300})
        page=ctx.new_page()
        status,err=safe_goto(page); s=sportsbook_frame(page)
        result.update({'portal_http_status':status,'navigation_error':err,'surface_url':s.url})
        result['league_clicked'],result['league_click_attempts']=click_exact(s,LEAGUE_LABEL)
        page.wait_for_timeout(1200)
        result['section_clicked'],result['section_click_attempts']=click_exact(s,SECTION_LABEL)
        page.wait_for_timeout(2200)
        snap=capture(s)
        result['snapshot']=snap
        result['parsed_srl_rows']=parse_srl(snap)
        b.close()
    # Parent event bindings come from related links in same section, retained raw.
    result['decision']='CURRENT_SRL_ROWS_CAPTURED' if result['section_clicked'] and result['parsed_srl_rows'] else 'SRL_DETAIL_ROWS_PENDING'
    (OUT/'srl.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines={}
    for r in result['parsed_srl_rows']:
        if r['line'] is not None: lines[str(r['line'])]=lines.get(str(r['line']),0)+1
    summary={
      'portal_http_status':result.get('portal_http_status'),'league_clicked':result.get('league_clicked'),'section_clicked':result.get('section_clicked'),
      'srl_rows':len(result['parsed_srl_rows']),'line_counts':lines,'related_links':len((result.get('snapshot') or {}).get('related',[])),'decision':result['decision']
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
