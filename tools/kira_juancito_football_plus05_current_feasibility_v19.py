from __future__ import annotations
import html,json,re
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_plus05_current_feasibility_v19');TZ=ZoneInfo('America/Santo_Domingo')
def c(x):return re.sub(r'\s+',' ',str(x or '').replace('\xa0',' ')).strip()
def norm(s):return html.unescape(str(s or '')).replace("\\'", "'").replace('\\n','\n').replace('\\r','')
def adec(a):
 a=float(a);return 1+a/100 if a>0 else 1+100/abs(a) if a<0 else None
def parse(body,label):
 s=norm(body);starts=list(re.finditer(r'newE\s*=\s*new\s+Event\((.*?)\);',s,re.S));out=[]
 for i,m in enumerate(starts):
  p=m.group(1)
  if not re.search(r"['\"]Soccer['\"]",p,re.I):continue
  h=re.match(r"\s*(-?\d+)\s*,\s*(\d+)\s*,\s*'([^']*)'\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)",p,re.S)
  if not h:continue
  hid,eid=int(h.group(1)),int(h.group(2));y,mo,d,hh,mm=map(int,h.groups()[3:8]);end=starts[i+1].start() if i+1<len(starts) else min(len(s),m.end()+15000);block=s[m.end():end]
  parts={};rx=re.compile(r"newP\s*=\s*new\s+Participant\(\s*(\d+)\s*,\s*([123])\s*,\s*'([^']*)'\s*,\s*'[^']*'\s*,\s*'[^']*'\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)",re.S)
  for q in rx.finditer(block):
   if int(q.group(1))==eid:parts[int(q.group(2))]={'name':c(q.group(3)),'ml':float(q.group(4)),'spread':float(q.group(5)),'spread_price':float(q.group(6))}
  ev={'menu':label,'header_id':hid,'event_id':eid,'title':c(h.group(3)),'date':f'{y:04d}-{mo:02d}-{d:02d}','time':f'{hh:02d}:{mm:02d}','parts':parts}
  if all(k in parts and parts[k]['ml']!=0 for k in (1,2,3)) and len({parts[k]['ml'] for k in (1,2,3)})>1:
   ds={k:adec(parts[k]['ml']) for k in (1,2,3)};inv={k:1/ds[k] for k in ds};z=sum(inv.values());ev['p_home_novig']=inv[1]/z;ev['p_away_novig']=inv[2]/z
  out.append(ev)
 return out
def dom_cells(page,label):
 try:rows=page.locator("[id^='ML_'],[id^='SZML_'],[id^='PS_'],[id^='SZPS_']").evaluate_all("els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),cls:typeof e.className==='string'?e.className:'',title:e.getAttribute('title')||''}))")
 except Exception:return []
 out=[]
 for x in rows:
  m=re.match(r'^(?:SZ)?(ML|PS)_(\d+)_([123])$',x['id'],re.I)
  if m:out.append({'menu':label,'family':m.group(1).upper(),'event_id':int(m.group(2)),'sel':int(m.group(3)),'id':x['id'],'text':c(x['text']),'cls':c(x['cls']),'title':c(x['title']),'actionable':'tooltip_addBet' in x['cls'] and 'cellCandado' not in x['cls']})
 return out
def main():
 OUT.mkdir(parents=True,exist_ok=True);now=datetime.now(TZ);current={'label':'initial'};net=[];cells=[];nav=[];r=None
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);page=b.new_page(viewport={'width':1600,'height':1800},locale='es-DO',timezone_id='America/Santo_Domingo')
  def resp(rsp):
   if 'juancitosport.com.do' not in rsp.url or rsp.request.resource_type not in {'xhr','fetch'}:return
   if '_method=RefreshSelectedHeader' not in rsp.url and '_method=GetUpcomingEvents' not in rsp.url:return
   try:evs=parse(rsp.text(),current['label'])
   except Exception:return
   if evs:net.extend(evs)
  page.on('response',resp)
  loaded=False
  for a in range(5):
   try:
    r=page.goto(START,wait_until='commit',timeout=45000);page.wait_for_timeout(12000)
    if page.locator('#tblSH_53').count():loaded=True;break
   except Exception as ex:nav.append(f'{a+1}:{type(ex).__name__}:{ex}')
   page.wait_for_timeout(2000)
  if not loaded:b.close();raise RuntimeError('BOSS soccer menu unavailable: '+' | '.join(nav))
  subs=page.locator('#tblSH_53 .colSubHeader').evaluate_all("els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()}))")
  attempts=[]
  for s in subs:
   if not re.match(r'^shdr\d+$',s['id']):continue
   current['label']=s['text'];rec={**s,'clicked':False}
   try:page.locator('#'+s['id']).click(force=True,timeout=7000);rec['clicked']=True;page.wait_for_timeout(1600);cells.extend(dom_cells(page,s['text']))
   except Exception as ex:rec['error']=f'{type(ex).__name__}:{ex}'
   attempts.append(rec)
  b.close()
 evmap={}
 for e in net:evmap[e['event_id']]=e
 cellmap=defaultdict(dict)
 for x in cells:cellmap[(x['family'],x['event_id'])][x['sel']]=x
 eligible=[];exact=[]
 for e in evmap.values():
  ml=cellmap.get(('ML',e['event_id']),{});ps=cellmap.get(('PS',e['event_id']),{})
  if not all(k in ml and ml[k]['actionable'] for k in (1,2,3)) or 'p_home_novig' not in e:continue
  ph,pa=e['p_home_novig'],e['p_away_novig']
  if ph==pa:continue
  sel=1 if ph>pa else 2;pf=max(ph,pa)
  if pf<.60:continue
  rec={'menu':e['menu'],'header_id':e['header_id'],'event_id':e['event_id'],'date':e['date'],'title':e['title'],'selected_side':'HOME' if sel==1 else 'AWAY','selected_team':e['parts'].get(sel,{}).get('name'),'p_favorite_novig':pf,'selected_main_spread':e['parts'].get(sel,{}).get('spread'),'selected_main_spread_price':e['parts'].get(sel,{}).get('spread_price'),'selected_ps_cell':ps.get(sel),'same_selected_plus0_5':False}
  rec['same_selected_plus0_5']=bool(e['parts'].get(sel,{}).get('spread')==0.5 and sel in ps and ps[sel]['actionable'])
  eligible.append(rec)
  if rec['same_selected_plus0_5']:exact.append(rec)
 by=defaultdict(list)
 for x in exact:by[x['date']].append(x)
 max3={d:sorted(v,key=lambda x:(-x['p_favorite_novig'],x['event_id']))[:3] for d,v in by.items()}
 dist=Counter(len(v) for v in max3.values())
 res={'captured_at_local':now.isoformat(),'http':r.status if r else None,'nav_errors':nav,'menu_attempts':attempts,'all_clicked':bool(attempts) and all(x.get('clicked') for x in attempts),'soccer_events_unique':len(evmap),'p060_favorite_events_with_actionable_1x2':len(eligible),'same_selected_favorite_plus0_5_main_actionable_events':len(exact),'dates_with_exact_same_selected_plus0_5':len(by),'max3_date_multiplicity':dict(sorted(dist.items())),'exact_rows':exact,'eligible_rows':eligible,'decision':'CURRENT_PUBLIC_MAIN_PLUS0_5_CAPACITY_PRESENT' if exact else 'CURRENT_PUBLIC_MAIN_PLUS0_5_CAPACITY_ZERO','guard':'Outcome-blind current contract feasibility only. Main/public PS cells only; hidden/authenticated alternate ladders are not inferred. No wager cell clicked.'}
 (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8');summ={k:res[k] for k in ['captured_at_local','all_clicked','soccer_events_unique','p060_favorite_events_with_actionable_1x2','same_selected_favorite_plus0_5_main_actionable_events','dates_with_exact_same_selected_plus0_5','max3_date_multiplicity','decision']};(OUT/'summary.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summ,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
