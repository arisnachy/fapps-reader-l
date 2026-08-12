from __future__ import annotations
import json,re,html
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_buy_points_global_v10'); TZ=ZoneInfo('America/Santo_Domingo')
def norm(s): return html.unescape(str(s or '')).replace("\\'","'").replace('\\n','\n').replace('\\r','')
def parse(body,label):
 s=norm(body); out=[]
 for m in re.finditer(r'newE\s*=\s*new\s+Event\((.*?)\);',s,re.S):
  p=m.group(1)
  if not re.search(r"['\"]Soccer['\"]",p,re.I): continue
  q=re.match(r"\s*(-?\d+)\s*,\s*(\d+)\s*,\s*'([^']*)'\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(-?\d+)",p,re.S)
  if not q: continue
  hid,eid=int(q.group(1)),int(q.group(2)); y,mo,d,hh,mm,lid=map(int,q.groups()[3:9])
  out.append({'menu':label,'header_id':hid,'event_id':eid,'event_title':q.group(3),'date':f'{y:04d}-{mo:02d}-{d:02d}','time':f'{hh:02d}:{mm:02d}','league_id':lid})
 return out

def main():
 OUT.mkdir(parents=True,exist_ok=True); now=datetime.now(TZ); current={'label':'initial'}; net=[]; nav=[]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True); p=b.new_page(viewport={'width':1600,'height':1800},locale='es-DO',timezone_id='America/Santo_Domingo')
  def onr(r):
   if 'juancitosport.com.do' not in r.url or r.request.resource_type not in {'xhr','fetch'}: return
   if '_method=RefreshSelectedHeader' not in r.url and '_method=GetUpcomingEvents' not in r.url:return
   try: net.extend(parse(r.text(),current['label']))
   except Exception: pass
  p.on('response',onr); loaded=False
  for a in range(3):
   try:
    p.goto(START,wait_until='commit',timeout=45000);p.wait_for_timeout(12000)
    if p.locator('#tblSH_53').count(): loaded=True;break
   except Exception as e:nav.append(f'{a+1}:{type(e).__name__}:{e}')
  if not loaded: b.close();raise RuntimeError('BOSS football menu unavailable: '+' | '.join(nav))
  buy=p.evaluate("""()=>((window.WagerSession&&WagerSession.PointsRule&&WagerSession.PointsRule.BuyDetails)||[]).map(x=>({LeagueId:x.LeagueId,BuyPointId:x.BuyPointId,OddsToLay:x.OddsToLay,OddsToTake:x.OddsToTake}))""")
  subs=p.locator('#tblSH_53 .colSubHeader').evaluate_all("els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()}))")
  attempts=[]
  for s in subs:
   if not re.match(r'^shdr\d+$',s['id']):continue
   current['label']=s['text']; rec={**s,'clicked':False}
   try:p.locator('#'+s['id']).click(force=True,timeout=7000);rec['clicked']=True;p.wait_for_timeout(1800)
   except Exception as e:rec['error']=f'{type(e).__name__}:{e}'
   attempts.append(rec)
  b.close()
 ev={x['event_id']:x for x in net}; events=list(ev.values()); bp={}
 for x in buy: bp.setdefault(int(x['LeagueId']),[]).append(float(x['BuyPointId']))
 bp={k:sorted(set(v)) for k,v in bp.items()}
 lids=sorted(set(x['league_id'] for x in events)); inter=sorted(set(lids)&set(bp))
 compatible=[{**x,'buy_points':bp[x['league_id']]} for x in events if x['league_id'] in bp]
 res={'captured_at_local':now.isoformat(),'nav_errors':nav,'all_clicked':bool(attempts) and all(x.get('clicked') for x in attempts),'soccer_events':len(events),'soccer_league_ids':lids,'buy_rule_league_ids':sorted(bp),'intersection_league_ids':inter,'soccer_events_with_buy_rules':len(compatible),'compatible_events':compatible,'buy_points_by_league':bp,'guard':'Read-only full Football menu + in-memory PointsRule intersection; no bet selection/coupon/account mutation.'}
 (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
 summ={k:res[k] for k in ['captured_at_local','nav_errors','all_clicked','soccer_events','soccer_league_ids','buy_rule_league_ids','intersection_league_ids','soccer_events_with_buy_rules']}
 (OUT/'summary.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summ,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
