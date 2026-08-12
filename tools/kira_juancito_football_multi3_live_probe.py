from __future__ import annotations

import json, math, re
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

PORTAL='https://www.juancitosport.com.do/deportes/'
OUT=Path('artifacts/kira_juancito_football_multi3_live')

def clean(v): return re.sub(r'\s+',' ',str(v or '')).strip()
def goto(p):
    try:r=p.goto(PORTAL,wait_until='commit',timeout=30000);st=r.status if r else None;er=''
    except PlaywrightTimeoutError as e:st=None;er=f'{type(e).__name__}: {e}'
    p.wait_for_timeout(6000);return st,er
def surf(p):
    for f in p.frames:
        if 'BOSSWagering/Sportsbook' in (f.url or ''): return f
    return p
def click_soccer(s):
    # Try operator labels only; no wager cells.
    attempts=[]
    for label in ('FÚTBOL','Fútbol','FUTBOL','Futbol','Soccer'):
        loc=s.get_by_text(label,exact=True)
        for i in range(loc.count()):
            n=loc.nth(i);m={'label':label,'index':i}
            try:
                m.update(n.evaluate("e=>({tag:e.tagName,id:e.id||'',cls:e.className||'',onclick:e.getAttribute('onclick')||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()})"));m['visible']=n.is_visible()
                if m['visible']:
                    n.click(force=True,timeout=6000);attempts.append({**m,'clicked':True});s.page.wait_for_timeout(2200);return True,attempts
            except Exception as e:m['error']=f'{type(e).__name__}: {e}'
            attempts.append(m)
    return False,attempts
def cap(s):
    return s.evaluate(r"""()=>{const c=x=>(x||'').replace(/\s+/g,' ').trim();return{
      body:c(document.body?document.body.innerText:'').slice(0,220000),
      ml:Array.from(document.querySelectorAll('[id]')).filter(e=>/^(SZ)?ML_\d+_[123]$/i.test(e.id||'')).map(e=>({id:e.id||'',text:c(e.innerText||e.textContent),row:c(e.closest('tr')?e.closest('tr').innerText||e.closest('tr').textContent:''),cls:e.className||''})).slice(0,12000),
      ps:Array.from(document.querySelectorAll('[id]')).filter(e=>/^(SZ)?PS_\d+_[123]$/i.test(e.id||'')).map(e=>({id:e.id||'',text:c(e.innerText||e.textContent),row:c(e.closest('tr')?e.closest('tr').innerText||e.closest('tr').textContent:''),cls:e.className||''})).slice(0,12000),
      related:Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e=>({text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''})).slice(0,3000),
      sectionHeads:Array.from(document.querySelectorAll('*')).filter(e=>/(Apuestas al partido|Game Lines|Primer Tiempo|1er Tiempo|First Half)/i.test(c(e.innerText||e.textContent)) && c(e.innerText||e.textContent).length<180).map(e=>({tag:e.tagName,id:e.id||'',cls:e.className||'',text:c(e.innerText||e.textContent)})).slice(0,1000)
    }}""")
def american(text):
    m=re.search(r'(?<!\d)([+-]\d{3,4})(?!\d)',clean(text))
    return int(m.group(1)) if m else None
def dec(a): return 1+a/100 if a>0 else 1+100/abs(a)
def groups(snap):
    g={}
    for x in snap['ml']:
        m=re.match(r'^(?:SZ)?ML_(\d+)_([123])$',x['id'],re.I)
        if not m:continue
        eid=int(m.group(1));sel=int(m.group(2));a=american(x['text'])
        if a is not None:g.setdefault(eid,{})[sel]={'american':a,'text':x['text'],'row':x['row']}
    out=[]
    for eid,d in g.items():
        if not all(k in d for k in (1,2,3)):continue
        ds={k:dec(d[k]['american']) for k in (1,2,3)};q={k:1/ds[k] for k in ds};z=sum(q.values());p={k:q[k]/z for k in q}
        out.append({'event_id':eid,'home_american':d[1]['american'],'away_american':d[2]['american'],'draw_american':d[3]['american'],'p_home_novig':p[1],'p_away_novig':p[2],'p_draw_novig':p[3],'home_row_text':d[1]['row']})
    return out
def refs(snap):
    out={}
    for x in snap['related']:
        m=re.search(r'RelatedEvents\((\d+)\s*,\s*(\d+)',x['onclick'])
        if m:out[int(m.group(2))]={'header_id':int(m.group(1)),'event_id':int(m.group(2)),'text':x['text']}
    return out
def related(s,h,e):
    try:
        if not s.evaluate("typeof RelatedEvents === 'function'"):return False,'RelatedEvents_missing'
        s.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[h,e]);s.page.wait_for_timeout(1700);return True,''
    except Exception as x:return False,f'{type(x).__name__}: {x}'
def plus15(snap,eid):
    rows=[]
    for x in snap['ps']:
        m=re.match(r'^(?:SZ)?PS_(\d+)_([123])$',x['id'],re.I)
        if not m or int(m.group(1))!=eid or int(m.group(2))!=1:continue
        txt=clean(x['text']); lm=re.search(r'([+-]\d+(?:\.5)?)\s+([+-]\d{3,4})',txt)
        if lm and abs(float(lm.group(1))-1.5)<1e-9:rows.append({'cell_id':x['id'],'line':1.5,'american_price':int(lm.group(2)),'text':txt,'row':x['row']})
    return rows

def main():
    OUT.mkdir(parents=True,exist_ok=True);res={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'read_only':True,'selector':'HOME p_home_novig>=0.75; top3 distinct events'}
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True);ctx=b.new_context(locale='es-DO',timezone_id='America/Santo_Domingo',viewport={'width':1440,'height':1400});p=ctx.new_page();st,er=goto(p);s=surf(p);res.update({'http':st,'nav_error':er,'surface':s.url})
        res['soccer_clicked'],res['soccer_attempts']=click_soccer(s);board=cap(s);res['board']=board;allg=groups(board);res['all_complete_1x2_events']=allg
        candidates=sorted([x for x in allg if x['p_home_novig']>=.75],key=lambda x:(-x['p_home_novig'],x['home_american'],x['event_id']))[:3];res['frozen_candidates_pre_handicap']=candidates; rr=refs(board); details=[]
        for c in candidates:
            ref=rr.get(c['event_id']);d={'candidate':c,'related_ref':ref}
            if not ref:d['state']='MARKET_DATA_PENDING_NO_RELATED_REF';details.append(d);continue
            ok,e=related(s,ref['header_id'],ref['event_id']);d['related_ok']=ok;d['related_error']=e
            if ok:
                snap=cap(s);d['detail_section_heads']=snap['sectionHeads'];d['plus1_5_home_rows']=plus15(snap,c['event_id']);body=snap['body'].lower();d['full_game_text_evidence']=('apuestas al partido' in body or 'game lines' in body) and not ('primer tiempo' in ' '.join(h['text'].lower() for h in snap['sectionHeads'][:10]))
                if len(d['plus1_5_home_rows'])==1 and d['full_game_text_evidence']:d['state']='CURRENT_CONTRACT_CANDIDATE_EXPLICIT_GAME_SECTION'
                elif d['plus1_5_home_rows']:d['state']='CURRENT_PLUS1_5_PERIOD_EVIDENCE_PENDING'
                else:d['state']='CURRENT_PLUS1_5_NOT_OBSERVED_IN_CAPTURE'
            details.append(d)
        res['details']=details;b.close()
    res['exact_plus1_5_candidates']=sum(1 for d in res['details'] if d.get('state')=='CURRENT_CONTRACT_CANDIDATE_EXPLICIT_GAME_SECTION')
    res['decision']='CURRENT_MULTI3_MARKET_CANDIDATES_OBSERVED' if res['exact_plus1_5_candidates'] else ('NO_ELIGIBLE_EVENT' if not res['frozen_candidates_pre_handicap'] else 'MARKET_DATA_PENDING_OR_UNAVAILABLE')
    (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8');summary={'http':res['http'],'soccer_clicked':res['soccer_clicked'],'complete_1x2_events':len(res['all_complete_1x2_events']),'frozen_candidates':len(res['frozen_candidates_pre_handicap']),'exact_plus1_5_candidates':res['exact_plus1_5_candidates'],'decision':res['decision']};(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
