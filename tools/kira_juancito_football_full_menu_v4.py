from __future__ import annotations
import html,json,re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_full_menu_v4'); TZ=ZoneInfo('America/Santo_Domingo')
def c(x): return re.sub(r'\s+',' ',str(x or '').replace('\xa0',' ')).strip()
def norm(s): return html.unescape(str(s or '')).replace("\\'", "'").replace('\\n','\n').replace('\\r','')
def adec(a): a=float(a); return 1+a/100 if a>0 else 1+100/abs(a) if a<0 else None
def parse(body,label):
 s=norm(body); starts=list(re.finditer(r'newE\s*=\s*new\s+Event\((.*?)\);',s,re.S)); out=[]
 for i,m in enumerate(starts):
  p=m.group(1)
  if not re.search(r"['\"]Soccer['\"]",p,re.I): continue
  h=re.match(r"\s*(-?\d+)\s*,\s*(\d+)\s*,\s*'([^']*)'\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)",p,re.S)
  if not h: continue
  hid,eid=int(h.group(1)),int(h.group(2)); y,mo,d,hh,mm=map(int,h.groups()[3:8]); end=starts[i+1].start() if i+1<len(starts) else min(len(s),m.end()+12000); block=s[m.end():end]
  parts={}; rx=re.compile(r"newP\s*=\s*new\s+Participant\(\s*(\d+)\s*,\s*([123])\s*,\s*'([^']*)'\s*,\s*'[^']*'\s*,\s*'[^']*'\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)",re.S)
  for q in rx.finditer(block):
   if int(q.group(1))==eid: parts[int(q.group(2))]={'name':c(q.group(3)),'ml':float(q.group(4)),'spread':float(q.group(5)),'spread_price':float(q.group(6))}
  ev={'menu':label,'header_id':hid,'event_id':eid,'title':c(h.group(3)),'date':f'{y:04d}-{mo:02d}-{d:02d}','time':f'{hh:02d}:{mm:02d}','parts':parts}
  if all(k in parts and parts[k]['ml']!=0 for k in (1,2,3)) and len({parts[k]['ml'] for k in (1,2,3)})>1:
   ds={k:adec(parts[k]['ml']) for k in (1,2,3)}; inv={k:1/ds[k] for k in ds}; z=sum(inv.values()); ev['p_home_novig']=inv[1]/z
  out.append(ev)
 return out

def dom_market(page,label):
 try: rows=page.locator("[id^='ML_'],[id^='SZML_']").evaluate_all("els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),cls:typeof e.className==='string'?e.className:'',title:e.getAttribute('title')||''}))")
 except Exception:return []
 out=[]
 for x in rows:
  m=re.match(r'^(?:SZ)?ML_(\d+)_([123])$',x['id'],re.I)
  if m: out.append({'menu':label,'event_id':int(m.group(1)),'sel':int(m.group(2)),'id':x['id'],'text':c(x['text']),'cls':c(x['cls']),'title':c(x['title']),'actionable':'tooltip_addBet' in x['cls'] and 'cellCandado' not in x['cls']})
 return out

def main():
 OUT.mkdir(parents=True,exist_ok=True); now=datetime.now(TZ); current={'label':'initial'}; net=[]; nav_errors=[]; r=None
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True); page=b.new_page(viewport={'width':1600,'height':1800},locale='es-DO',timezone_id='America/Santo_Domingo')
  def resp(rsp):
   if 'juancitosport.com.do' not in rsp.url or rsp.request.resource_type not in {'xhr','fetch'}: return
   if '_method=RefreshSelectedHeader' not in rsp.url and '_method=GetUpcomingEvents' not in rsp.url:return
   try: body=rsp.text()
   except Exception:return
   evs=parse(body,current['label'])
   if evs: net.extend(evs)
  page.on('response',resp)
  for attempt in range(1,4):
   try:
    r=page.goto(START,wait_until='commit',timeout=45000)
    page.wait_for_timeout(14000)
    if page.locator('#tblSH_53').count(): break
    nav_errors.append(f'attempt {attempt}: tblSH_53 missing after committed navigation; url={page.url}')
   except Exception as e:
    nav_errors.append(f'attempt {attempt}: {type(e).__name__}: {e}')
   try: page.wait_for_timeout(3000)
   except Exception: pass
  if not page.locator('#tblSH_53').count():
   b.close(); raise RuntimeError('BOSS soccer menu tblSH_53 not loaded: '+' | '.join(nav_errors))
  subs=page.locator('#tblSH_53 .colSubHeader').evaluate_all("els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),visible:!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)}))")
  attempts=[]; markets=[]
  for s in subs:
   if not re.match(r'^shdr\d+$',s['id']): continue
   current['label']=s['text']; rec={**s,'clicked':False}
   try:
    page.locator('#'+s['id']).click(force=True,timeout=7000);rec['clicked']=True;page.wait_for_timeout(1800);markets.extend(dom_market(page,s['text']))
   except Exception as e:rec['error']=f'{type(e).__name__}:{e}'
   attempts.append(rec)
  b.close()
 ev={}
 for x in net: ev[x['event_id']]=x
 events=list(ev.values()); ml_by={}
 for x in markets: ml_by.setdefault(x['event_id'],{})[x['sel']]=x
 actionable=[]
 for x in events:
  cells=ml_by.get(x['event_id'],{}); x['ml_cells']=cells
  x['complete_actionable_1x2']=all(k in cells and cells[k]['actionable'] for k in (1,2,3))
  if x['complete_actionable_1x2']: actionable.append(x)
 priced=[x for x in actionable if 'p_home_novig' in x]
 cand=[x for x in priced if x['p_home_novig']>=.75]
 today=str(now.date()); today_e=[x for x in actionable if x['date']==today]; today_c=[x for x in cand if x['date']==today]
 res={'captured_at_local':now.isoformat(),'http':r.status if r else None,'nav_errors':nav_errors,'football_menu_subheaders':subs,'menu_attempts':attempts,'all_clicked':bool(attempts) and all(x.get('clicked') for x in attempts),'soccer_events_seen_unique':len(events),'complete_actionable_1x2_events':len(actionable),'priced_actionable_events':len(priced),'home_p075_candidates_current_catalog':len(cand),'today_actionable_events':len(today_e),'today_home_p075_candidates':len(today_c),'events':events,'candidates':cand,'coverage_complete_public_menu':bool(attempts) and all(x.get('clicked') for x in attempts),'guard':'Read-only public football menu traversal. No bet cells clicked; market cells only read.'}
 (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8'); summary={k:res[k] for k in ['captured_at_local','nav_errors','football_menu_subheaders','menu_attempts','all_clicked','soccer_events_seen_unique','complete_actionable_1x2_events','priced_actionable_events','home_p075_candidates_current_catalog','today_actionable_events','today_home_p075_candidates','coverage_complete_public_menu']};(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
