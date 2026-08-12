from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_team_total_census_v11'); TZ=ZoneInfo('America/Santo_Domingo')
def c(x):return re.sub(r'\s+',' ',str(x or '').replace('\xa0',' ')).strip()
def scan(page,label):
 try:
  cells=page.locator("[id^='TTT_'],[id^='SZTTT_']").evaluate_all("els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),cls:typeof e.className==='string'?e.className:'',title:e.getAttribute('title')||''}))")
 except Exception:return []
 out=[]
 for x in cells:
  m=re.match(r'^(?:SZ)?TTT_(\d+)_([123])$',x['id'],re.I)
  if m:out.append({'menu':label,'event_id':int(m.group(1)),'sel':int(m.group(2)),'id':x['id'],'text':c(x['text']),'cls':c(x['cls']),'title':c(x['title']),'actionable':'tooltip_addBet' in x['cls'] and 'cellCandado' not in x['cls']})
 return out
def main():
 OUT.mkdir(parents=True,exist_ok=True);now=datetime.now(TZ);nav=[];rows=[];attempts=[]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=pw.chromium.launch if False else b.new_page(viewport={'width':1600,'height':1800},locale='es-DO',timezone_id='America/Santo_Domingo')
  loaded=False
  for a in range(3):
   try:
    p.goto(START,wait_until='commit',timeout=45000);p.wait_for_timeout(12000)
    if p.locator('#tblSH_53').count():loaded=True;break
   except Exception as e:nav.append(f'{a+1}:{type(e).__name__}:{e}')
  if not loaded:b.close();raise RuntimeError('BOSS football menu unavailable: '+' | '.join(nav))
  subs=p.locator('#tblSH_53 .colSubHeader').evaluate_all("els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()}))")
  for s in subs:
   if not re.match(r'^shdr\d+$',s['id']):continue
   rec={**s,'clicked':False}
   try:
    p.locator('#'+s['id']).click(force=True,timeout=7000);rec['clicked']=True;p.wait_for_timeout(1800);rows.extend(scan(p,s['text']))
   except Exception as e:rec['error']=f'{type(e).__name__}:{e}'
   attempts.append(rec)
  b.close()
 uniq={(x['event_id'],x['sel']):x for x in rows};cells=list(uniq.values());action=[x for x in cells if x['actionable'] and x['text']]
 events=sorted(set(x['event_id'] for x in action));line_text_counts={}
 for x in action:line_text_counts[x['text']]=line_text_counts.get(x['text'],0)+1
 res={'captured_at_local':now.isoformat(),'nav_errors':nav,'all_clicked':bool(attempts) and all(x.get('clicked') for x in attempts),'team_total_cells_seen':len(cells),'actionable_team_total_cells':len(action),'events_with_actionable_team_total':len(events),'event_ids':events,'line_text_counts':dict(sorted(line_text_counts.items(),key=lambda kv:(-kv[1],kv[0]))),'actionable_cells':action,'guard':'Read-only Football Team Total DOM census; no bet cell click/coupon/account mutation.'}
 (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8');summ={k:res[k] for k in ['captured_at_local','nav_errors','all_clicked','team_total_cells_seen','actionable_team_total_cells','events_with_actionable_team_total','line_text_counts']};(OUT/'summary.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summ,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
