from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_buy_points_options_v8')
TZ=ZoneInfo('America/Santo_Domingo')
EVENTS=[(2538,1963283,'PORTUGAL','Benfica-Casa Pia'),(1915,1956300,'AUSTRALIA','Heidelberg-North Sunshine'),(2878,1964294,'GUATEMALA','AFF-Fraijanes'),(2203,1963977,'N IRELAND','ST James-Bangor')]

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True)
  p=b.new_page(viewport={'width':1600,'height':1800},locale='es-DO',timezone_id='America/Santo_Domingo')
  p.goto(START,wait_until='commit',timeout=60000);p.wait_for_timeout(12000)
  pr=p.evaluate("""()=>{
   const ws=window.WagerSession; const r=ws&&ws.PointsRule;
   function props(x){ if(!x)return null; let o={}; for(const k in x){ try{let v=x[k]; if(typeof v!=='function' && (v===null || ['string','number','boolean'].includes(typeof v)))o[k]=v;}catch(e){} } return o; }
   return {hasWS:!!ws,hasPointsRule:!!r,buy:(r&&r.BuyDetails||[]).map(props),sell:(r&&r.SellDetails||[]).map(props),sensitive:(r&&r.SensitiveDetails||[]).map(props)};
  }""")
  probes=[]
  for h,e,menu,label in EVENTS:
   try:
    p.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[h,e]);p.wait_for_timeout(3000)
   except Exception as ex:
    probes.append({'event_id':e,'label':label,'error':str(ex)});continue
   rec={'event_id':e,'label':label,'menu':menu,'spread_cells':[]}
   for side in [1,2]:
    loc=p.locator(f'#PS_{e}_{side}')
    if not loc.count(): continue
    try:
     rec['spread_cells'].append({'side':side,'text':loc.inner_text(),'outer_html':loc.evaluate('(e)=>e.outerHTML')[:12000]})
    except Exception as ex: rec['spread_cells'].append({'side':side,'error':str(ex)})
   # Collect scripts/inline HTML fragments that mention the event id and rule/league fields.
   try:
    html=p.content();
    snippets=[]
    for m in re.finditer(str(e),html):
     s=max(0,m.start()-900);z=min(len(html),m.end()+1400);frag=re.sub(r'\s+',' ',html[s:z])
     if any(k.lower() in frag.lower() for k in ['league','rule','ps_','point','onclick']): snippets.append(frag)
     if len(snippets)>=12: break
    rec['event_html_snippets']=snippets
   except Exception: pass
   probes.append(rec)
  result={'captured_at_local':datetime.now(TZ).isoformat(),'points_rule':pr,'event_probes':probes,'guard':'Read-only global state/DOM inspection. No wager creation, bet-cell click, coupon or account mutation.'}
  (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  buy=pr.get('buy') or []
  byleague={}
  for x in buy:
   lid=x.get('LeagueId'); bp=x.get('BuyPointId');
   if lid is not None and bp is not None: byleague.setdefault(str(lid),[]).append(bp)
  byleague={k:sorted(set(v)) for k,v in byleague.items()}
  summary={'captured_at_local':result['captured_at_local'],'has_points_rule':pr.get('hasPointsRule'),'buy_detail_count':len(buy),'sell_detail_count':len(pr.get('sell') or []),'buy_points_by_league':byleague,'events_probed':len(probes)}
  (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps(summary,ensure_ascii=False,indent=2))
  b.close()
if __name__=='__main__':main()
