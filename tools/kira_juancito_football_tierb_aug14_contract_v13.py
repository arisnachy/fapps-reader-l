from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_tierb_aug14_contract_v13');TZ=ZoneInfo('America/Santo_Domingo')
# Exact Tier-B source-universe compatible current candidates on 2026-08-14 from V4 capture.
# First three are deterministic global max3 by p_favorite; remaining two audited as depth only.
TARGETS=[
 (2037,1961877,'CHINA','Shandong Luneng Taishan','AWAY',0.6654271992,1),
 (2015,1962330,'POLAND','Ruch Chorzow','AWAY',0.6311341126,2),
 (2059,1959023,'AUSTRIA','LASK Linz','AWAY',0.6047688012,3),
 (1932,1963327,'BRAZIL','Sport Club Recife PE','AWAY',0.5662690092,4),
 (2019,1961879,'FINLAND','VPS - Vaasan Palloseura','AWAY',0.5540667576,5),
]
def c(x):return re.sub(r'\s+',' ',str(x or '').replace('\xa0',' ')).strip()
def main():
 OUT.mkdir(parents=True,exist_ok=True);nav=[];results=[]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':1800,'height':2200},locale='es-DO',timezone_id='America/Santo_Domingo')
  loaded=False
  for a in range(4):
   try:
    p.goto(START,wait_until='commit',timeout=45000);p.wait_for_timeout(10000)
    if p.locator('#tblSH_53').count():loaded=True;break
   except Exception as ex:nav.append(f'{a+1}:{type(ex).__name__}:{ex}')
  if not loaded:b.close();raise RuntimeError('BOSS unavailable: '+' | '.join(nav))
  for h,e,country,team,side,pfav,rank in TARGETS:
   rec={'header_id':h,'event_id':e,'country':country,'selected_team':team,'selected_side':side,'p_favorite_novig':pfav,'tierb_rank':rank}
   try:p.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[h,e]);p.wait_for_timeout(3500)
   except Exception as ex:rec['related_error']=f'{type(ex).__name__}:{ex}';results.append(rec);continue
   try:
    els=p.locator(f"[id*='{e}']").evaluate_all("""els=>els.map(x=>({tag:x.tagName,id:x.id||'',cls:typeof x.className==='string'?x.className:'',text:(x.innerText||x.textContent||'').replace(/\\s+/g,' ').trim(),title:x.getAttribute('title')||'',name:x.getAttribute('name')||'',value:x.getAttribute('value')||'',onclick:x.getAttribute('onclick')||'',html:x.outerHTML.slice(0,10000)}))""")
   except Exception as ex:els=[];rec['els_error']=str(ex)
   rec['event_elements']=els[:400]
   rec['actionable']=[x for x in els if 'tooltip_addBet' in x.get('cls','') and 'cellCandado' not in x.get('cls','')]
   # Conservative exact selected-team +1.5: require +1½/+1.5 on same event-associated element and selected-team identity in that element or its row HTML.
   hits=[]
   for x in els:
    txt=x.get('text','');blob=(txt+' '+x.get('title','')+' '+x.get('html','')).lower()
    hasline=('+1½' in txt or '+1.5' in txt or re.search(r'(?<!-)\b1½\b',txt) is not None)
    if hasline and team.lower() in blob:hits.append(x)
   rec['selected_plus15_hits']=hits
   # Capture smallest containers carrying literal Team Total and event id for secondary route discovery.
   try:
    rec['team_total_containers']=p.locator('table,div').evaluate_all("""(els,eid)=>els.map(x=>({id:x.id||'',cls:typeof x.className==='string'?x.className:'',text:(x.innerText||x.textContent||'').replace(/\\s+/g,' ').trim(),html:x.outerHTML.slice(0,40000)})).filter(x=>x.text.toLowerCase().includes('team total') && x.html.includes(String(eid))).sort((a,b)=>a.text.length-b.text.length).slice(0,8)""",e)
   except Exception as ex:rec['team_total_containers']=[];rec['container_error']=str(ex)
   try:
    rec['selects']=p.locator('select').evaluate_all("""els=>els.map(s=>({id:s.id||'',name:s.name||'',value:s.value||'',text:(s.innerText||s.textContent||'').replace(/\\s+/g,' ').trim(),options:[...s.options].map(o=>({text:(o.textContent||'').trim(),value:o.value,selected:o.selected,disabled:o.disabled}))})).filter(x=>x.id||x.name).slice(0,150)""")
   except Exception:rec['selects']=[]
   results.append(rec)
  b.close()
 res={'captured_at_local':datetime.now(TZ).isoformat(),'nav_errors':nav,'targets':len(TARGETS),'results':results,'guard':'Read-only exact-contract audit. No wager cell click, no coupon/account mutation.'}
 (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
 summ={'captured_at_local':res['captured_at_local'],'nav_errors':nav,'per_event':[{'rank':x['tierb_rank'],'event_id':x['event_id'],'team':x['selected_team'],'country':x['country'],'actionable_elements':len(x.get('actionable',[])),'selected_plus15_hits':len(x.get('selected_plus15_hits',[])),'team_total_containers':len(x.get('team_total_containers',[])),'error':x.get('related_error')} for x in results]}
 (OUT/'summary.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summ,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
