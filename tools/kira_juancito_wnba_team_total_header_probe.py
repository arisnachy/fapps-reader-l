from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
PORTAL='https://www.juancitosport.com.do/deportes/'
OUT=Path('artifacts/kira_juancito_wnba_tt_header')

def clean(v):return re.sub(r'\s+',' ',str(v or '')).strip()
def goto(p):
    try:r=p.goto(PORTAL,wait_until='commit',timeout=30000); st=r.status if r else None;err=''
    except PlaywrightTimeoutError as e:st=None;err=f'{type(e).__name__}: {e}'
    p.wait_for_timeout(6000);return st,err
def surf(p):
    for f in p.frames:
        if 'BOSSWagering/Sportsbook' in (f.url or ''):return f
    return p
def click(s,label,exact=True):
    loc=s.get_by_text(label,exact=exact); out=[]
    for i in range(loc.count()):
        n=loc.nth(i);m={'index':i}
        try:
            m.update(n.evaluate("e=>({tag:e.tagName,id:e.id||'',cls:e.className||'',onclick:e.getAttribute('onclick')||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()})"));m['visible']=n.is_visible()
            if m['visible']:
                n.scroll_into_view_if_needed(timeout=3000);n.click(force=True,timeout=6000);out.append({**m,'clicked':True});return True,out
        except Exception as e:m['error']=f'{type(e).__name__}: {e}'
        out.append(m)
    return False,out
def cap(s):
    return s.evaluate(r"""()=>{const c=x=>(x||'').replace(/\s+/g,' ').trim();return{
      body:c(document.body?document.body.innerText:'').slice(0,180000),
      selects:Array.from(document.querySelectorAll('select')).map((e,i)=>({index:i,id:e.id||'',name:e.name||'',aria:e.getAttribute('aria-label')||'',title:e.getAttribute('title')||'',row:c(e.closest('tr')?e.closest('tr').innerText||e.closest('tr').textContent:''),ctx:c(e.closest('td,tr,div')?e.closest('td,tr,div').innerText||e.closest('td,tr,div').textContent:''),options:Array.from(e.options||[]).slice(0,150).map(o=>({text:c(o.textContent),value:o.value,selected:o.selected,disabled:o.disabled}))})).slice(0,1000),
      cells:Array.from(document.querySelectorAll('[id]')).filter(e=>/^(SZ)?(ML|PS|TT)_\d+_/i.test(e.id||'')).map(e=>({id:e.id||'',text:c(e.innerText||e.textContent),row:c(e.closest('tr')?e.closest('tr').innerText||e.closest('tr').textContent:''),cls:e.className||''})).slice(0,10000),
      ttHeads:Array.from(document.querySelectorAll('*')).filter(e=>c(e.innerText||e.textContent)==='Team Total').map(e=>({tag:e.tagName,id:e.id||'',cls:e.className||'',onclick:e.getAttribute('onclick')||'',parent_onclick:e.parentElement?e.parentElement.getAttribute('onclick')||'':'',outer:e.outerHTML.slice(0,2500)})).slice(0,50),
      related:Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e=>({text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''})).slice(0,500)
    }}""")
def refs(snap):
    out=[]
    for x in snap['related']:
        m=re.search(r'RelatedEvents\((\d+)\s*,\s*(\d+)',x['onclick'])
        if m:out.append((int(m.group(1)),int(m.group(2)),clean(x['text'])))
    return list(dict.fromkeys(out))
def related(s,h,e):
    try:s.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[h,e]);s.page.wait_for_timeout(1600);return True,''
    except Exception as x:return False,f'{type(x).__name__}: {x}'
def main():
    OUT.mkdir(parents=True,exist_ok=True);res={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'read_only':True}
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True);ctx=b.new_context(locale='es-DO',timezone_id='America/Santo_Domingo');p=ctx.new_page();st,er=goto(p);s=surf(p);res.update({'http':st,'nav_error':er,'surface':s.url})
        res['wnba_clicked'],res['wnba_attempts']=click(s,'WNBA');p.wait_for_timeout(1200);board=cap(s);rr=refs(board);res['refs']=rr;details=[]
        for h,e,t in rr[:20]:
            ok,err=related(s,h,e);d={'header_id':h,'event_id':e,'text':t,'related_ok':ok,'related_error':err}
            if ok:
                before=cap(s);d['before_tt_heads']=before['ttHeads'];clicked,att=click(s,'Team Total');d['tt_clicked']=clicked;d['tt_click_attempts']=att;p.wait_for_timeout(1800);after=cap(s);d['after']=after
                # Keep any select whose context mentions Team Total or has plausible team-total basketball numbers.
                hints=[]
                for sel in after['selects']:
                    txt=' | '.join([clean(sel['row']),clean(sel['ctx']),' / '.join(clean(o['text']) for o in sel['options'])])
                    nums=[]
                    for n in re.findall(r'(?<!\d)(\d+(?:½|\.5)?)(?!\d)',txt):
                        try: nums.append(float(n.replace('½','.5')))
                        except:pass
                    if 'team total' in txt.lower() or any(45<=n<=105 for n in nums):hints.append({'select':sel,'numbers':sorted(set(nums)),'text':txt[:3000]})
                d['hints']=hints
            details.append(d)
        res['details']=details;b.close()
    protective=[]
    for d in details:
        for h in d.get('hints',[]):
            lows=[n for n in h['numbers'] if 45<=n<=65]
            if lows:protective.append({'event_id':d['event_id'],'event_text':d['text'],'low_lines':lows,'text':h['text']})
    res['protective_45_65']=protective;res['decision']='PROTECTIVE_TEAM_TOTAL_OPTIONS_OBSERVED' if protective else 'TEAM_TOTAL_HEADER_PROBED_NO_PROTECTIVE_OPTION_PROVEN'
    (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8');summary={'http':res['http'],'refs':len(rr),'details':len(details),'tt_clicked':sum(d.get('tt_clicked',False) for d in details),'selects_after':sum(len(d.get('after',{}).get('selects',[])) for d in details),'protective_hints':len(protective),'decision':res['decision']};(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
