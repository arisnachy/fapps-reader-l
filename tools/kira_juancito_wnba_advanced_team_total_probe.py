from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL="https://www.juancitosport.com.do/deportes/"
OUT=Path("artifacts/kira_juancito_wnba_advanced_tt")


def clean(v): return re.sub(r"\s+"," ",str(v or "")).strip()

def safe_goto(page):
    status=None; err=""
    try:
        r=page.goto(PORTAL_URL,wait_until="commit",timeout=30000); status=r.status if r else None
    except PlaywrightTimeoutError as exc: err=f"{type(exc).__name__}: {exc}"
    page.wait_for_timeout(6000); return status,err

def surface(page):
    for f in page.frames:
        if "BOSSWagering/Sportsbook" in (f.url or ""): return f
    return page

def click_visible_text(s,pattern,exact=False):
    loc=s.get_by_text(pattern,exact=exact); attempts=[]
    for i in range(loc.count()):
        n=loc.nth(i); meta={"index":i}
        try:
            meta.update(n.evaluate("e=>({tag:e.tagName,id:e.id||'',cls:e.className||'',onclick:e.getAttribute('onclick')||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()})"))
            meta['visible']=n.is_visible()
            if meta['visible']:
                n.scroll_into_view_if_needed(timeout=3000); n.click(force=True,timeout=6000); attempts.append({**meta,'clicked':True}); return True,attempts
        except Exception as exc: meta['error']=f"{type(exc).__name__}: {exc}"
        attempts.append(meta)
    return False,attempts

def capture(s):
    return s.evaluate(r"""
    () => {const c=x=>(x||'').replace(/\s+/g,' ').trim(); return {
      body:c(document.body?document.body.innerText:'').slice(0,180000),
      related:Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e=>({text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''})).slice(0,1500),
      selects:Array.from(document.querySelectorAll('select')).map((e,i)=>({index:i,id:e.id||'',name:e.name||'',aria:e.getAttribute('aria-label')||'',title:e.getAttribute('title')||'',row_text:c(e.closest('tr')?e.closest('tr').innerText||e.closest('tr').textContent:''),context:c(e.closest('td,tr,div')?e.closest('td,tr,div').innerText||e.closest('td,tr,div').textContent:''),options:Array.from(e.options||[]).slice(0,120).map(o=>({text:c(o.textContent),value:o.value,selected:o.selected,disabled:o.disabled}))})).slice(0,800),
      cells:Array.from(document.querySelectorAll('[id]')).filter(e=>/^(SZ)?(ML|PS|TT)_\d+_/i.test(e.id||'')).map(e=>({id:e.id||'',text:c(e.innerText||e.textContent),title:e.getAttribute('title')||'',aria:e.getAttribute('aria-label')||'',row_text:c(e.closest('tr')?e.closest('tr').innerText||e.closest('tr').textContent:'')})).slice(0,10000),
      adv:Array.from(document.querySelectorAll('*')).filter(e=>/(Advanced Player and Game Props|Props avanzadas|Propuestas avanzadas|Team Total|Total.*equipo)/i.test(c(e.innerText||e.textContent)) && c(e.innerText||e.textContent).length<500).map(e=>({tag:e.tagName,id:e.id||'',cls:e.className||'',onclick:e.getAttribute('onclick')||'',text:c(e.innerText||e.textContent)})).slice(0,1000)
    }}
    """)

def related_refs(snap):
    out=[]
    for link in snap.get('related',[]):
        m=re.search(r'RelatedEvents\((\d+)\s*,\s*(\d+)',link.get('onclick',''))
        if m: out.append({'header_id':int(m.group(1)),'event_id':int(m.group(2)),'text':clean(link.get('text'))})
    seen={}
    for x in out: seen[(x['header_id'],x['event_id'])]=x
    return list(seen.values())

def call_related(s,h,e):
    try:
        if not s.evaluate("typeof RelatedEvents === 'function'"): return False,'RelatedEvents_missing'
        s.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[h,e]); s.page.wait_for_timeout(1800); return True,''
    except Exception as exc: return False,f"{type(exc).__name__}: {exc}"

def tt_hints(snapshot):
    hints=[]
    rx=re.compile(r'team total|total.*equipo|equipo.*total',re.I)
    for sel in snapshot.get('selects',[]):
        text=' | '.join([clean(sel.get('row_text')),clean(sel.get('context')),' / '.join(clean(o.get('text')) for o in sel.get('options',[]))])
        nums=sorted(set(float(x) for x in re.findall(r'(?<!\d)(\d+(?:\.5)?)(?!\d)',text) if 20<=float(x)<=120))
        if rx.search(text) or nums:
            hints.append({'kind':'select','id':sel.get('id'),'text':text[:2500],'numeric_options_20_120':nums})
    for cell in snapshot.get('cells',[]):
        text=' | '.join([clean(cell.get('id')),clean(cell.get('text')),clean(cell.get('row_text'))])
        if rx.search(text): hints.append({'kind':'cell','id':cell.get('id'),'text':text[:1500]})
    return hints

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'read_only':True,'science_status':'NO_PROMOTION_FROM_MARKET_DISCOVERY'}
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True); ctx=b.new_context(locale='es-DO',timezone_id='America/Santo_Domingo',viewport={'width':1440,'height':1400}); page=ctx.new_page()
        status,err=safe_goto(page); s=surface(page); result.update({'portal_http_status':status,'navigation_error':err,'surface_url':s.url})
        result['wnba_clicked'],result['wnba_click_attempts']=click_visible_text(s,'WNBA',exact=True); page.wait_for_timeout(1800)
        board=capture(s); result['board']=board; refs=related_refs(board); result['board_related_refs']=refs
        details=[]
        for ref in refs[:30]:
            ok,e=call_related(s,ref['header_id'],ref['event_id']); rec={'ref':ref,'called':ok,'error':e}
            if ok:
                before=capture(s); rec['before']=before
                # Try only visible explicit Advanced Player/Game Props elements; never wager cells.
                clicked=False; attempts=[]
                for label in ('Advanced Player and Game Props','Propuestas avanzadas','Props avanzadas'):
                    clicked,attempts=click_visible_text(s,label,exact=True)
                    if clicked: break
                rec['advanced_clicked']=clicked; rec['advanced_click_attempts']=attempts
                if clicked: page.wait_for_timeout(1700)
                after=capture(s); rec['after']=after; rec['tt_hints']=tt_hints(after)
            details.append(rec)
        result['details']=details; b.close()
    all_hints=[]
    for d in result['details']:
        for h in d.get('tt_hints',[]): all_hints.append({'ref':d['ref'],**h})
    result['all_tt_hints']=all_hints
    exact_low=[]
    for h in all_hints:
        vals=h.get('numeric_options_20_120') or []
        lows=[v for v in vals if 45<=v<=65]
        if lows: exact_low.append({**h,'protective_45_65':lows})
    result['protective_45_65_hints']=exact_low
    result['decision']='PROTECTIVE_WNBA_TT_LADDER_OBSERVED' if exact_low else ('ADVANCED_TT_EVIDENCE_OBSERVED_NONPROTECTIVE_OR_UNRESOLVED' if all_hints else 'WNBA_ADVANCED_TT_MARKET_DATA_PENDING')
    (OUT/'wnba_advanced_tt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'portal_http_status':result.get('portal_http_status'),'wnba_clicked':result.get('wnba_clicked'),'related_refs':len(refs),'details_called':sum(d.get('called',False) for d in details),'advanced_clicked':sum(d.get('advanced_clicked',False) for d in details),'tt_hint_count':len(all_hints),'protective_45_65_hint_count':len(exact_low),'decision':result['decision']}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8'); print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
