from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_tierb6_deep_dom_v12'); TZ=ZoneInfo('America/Santo_Domingo')
# Frozen from full-menu V4 p_fav_novig>=.55, date 2026-08-12 only.
TARGETS=[
 (1915,1956300,'Heidelberg United','HOME'),
 (1915,1956311,'Preston Lions','HOME'),
 (2203,1963977,'Bangor W','AWAY'),
 (2878,1964294,'Fraijanes FC','AWAY'),
 (2878,1964303,'Mictlan','AWAY'),
 (2236,1964319,'Aucas','HOME'),
]
def c(x):return re.sub(r'\s+',' ',str(x or '').replace('\xa0',' ')).strip()
def main():
 OUT.mkdir(parents=True,exist_ok=True); nav=[]; results=[]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True); p=b.new_page(viewport={'width':1800,'height':2200},locale='es-DO',timezone_id='America/Santo_Domingo')
  loaded=False
  for a in range(4):
   try:
    p.goto(START,wait_until='commit',timeout=45000);p.wait_for_timeout(10000)
    if p.locator('#tblSH_53').count(): loaded=True;break
   except Exception as e:nav.append(f'{a+1}:{type(e).__name__}:{e}')
  if not loaded:b.close();raise RuntimeError('BOSS unavailable: '+' | '.join(nav))
  for h,e,team,side in TARGETS:
   rec={'header_id':h,'event_id':e,'selected_team':team,'selected_side':side}
   try:p.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[h,e]);p.wait_for_timeout(3500)
   except Exception as ex:rec['related_error']=f'{type(ex).__name__}:{ex}';results.append(rec);continue
   # Every event-associated element, bounded, preserving IDs/classes/text/title/data/outerHTML.
   try:
    els=p.locator(f"[id*='{e}']").evaluate_all("""els=>els.map(x=>({tag:x.tagName,id:x.id||'',cls:typeof x.className==='string'?x.className:'',text:(x.innerText||x.textContent||'').replace(/\\s+/g,' ').trim(),title:x.getAttribute('title')||'',name:x.getAttribute('name')||'',value:x.getAttribute('value')||'',onclick:x.getAttribute('onclick')||'',html:x.outerHTML.slice(0,6000)}))""")
   except Exception as ex:els=[];rec['els_error']=str(ex)
   rec['event_elements']=els[:300]
   # All SELECTs/options currently rendered; Team Total often uses select ladders.
   try:
    sels=p.locator('select').evaluate_all("""els=>els.map(s=>({id:s.id||'',name:s.name||'',cls:typeof s.className==='string'?s.className:'',value:s.value||'',text:(s.innerText||s.textContent||'').replace(/\\s+/g,' ').trim(),options:[...s.options].map(o=>({text:(o.textContent||'').trim(),value:o.value,selected:o.selected,disabled:o.disabled}))})).filter(x=>x.id.includes('"""+str(e)+"""')||x.name.includes('"""+str(e)+"""')||x.text.length<500)""")
   except Exception as ex:sels=[];rec['select_error']=str(ex)
   rec['selects']=sels[:100]
   # Nearby table/section outerHTML containing literal Team Total + event id.
   try:
    candidates=p.locator("table,div").evaluate_all("""(els,eid)=>els.map(x=>({id:x.id||'',cls:typeof x.className==='string'?x.className:'',text:(x.innerText||x.textContent||'').replace(/\\s+/g,' ').trim(),html:x.outerHTML.slice(0,30000)})).filter(x=>x.text.toLowerCase().includes('team total') && (x.html.includes(String(eid))||x.text.length<5000)).sort((a,b)=>a.text.length-b.text.length).slice(0,12)""",e)
   except Exception as ex:candidates=[];rec['container_error']=str(ex)
   rec['team_total_containers']=candidates
   # Compact extraction of actionable-looking cells for this event.
   rec['actionable']=[x for x in els if 'tooltip_addBet' in x.get('cls','') and 'cellCandado' not in x.get('cls','')]
   rec['plus15_selected_hits']=[x for x in els if ('+1½' in x.get('text','') or '+1.5' in x.get('text','') or '1½' in x.get('text','')) and team.lower() in (x.get('html','')+' '+x.get('text','')).lower()]
   results.append(rec)
  b.close()
 res={'captured_at_local':datetime.now(TZ).isoformat(),'nav_errors':nav,'targets':len(TARGETS),'results':results,'guard':'Read-only RelatedEvents/DOM inspection. No betting cell click, no coupon/account mutation.'}
 (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
 summ={'captured_at_local':res['captured_at_local'],'nav_errors':nav,'targets':len(TARGETS),'per_event':[{'event_id':x['event_id'],'team':x['selected_team'],'elements':len(x.get('event_elements',[])),'selects':len(x.get('selects',[])),'actionable':len(x.get('actionable',[])),'tt_containers':len(x.get('team_total_containers',[])),'selected_plus15_hits':len(x.get('plus15_selected_hits',[])),'error':x.get('related_error')} for x in results]}
 (OUT/'summary.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summ,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
