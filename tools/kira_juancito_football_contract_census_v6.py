from __future__ import annotations
import json,re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_contract_census_v6')
TZ=ZoneInfo('America/Santo_Domingo')
# Frozen from full-menu V4 capture 2026-08-11 22:33 RD; all are 2026-08-12 complete actionable 1X2.
TARGETS=[
 (2007,1958169,'ARGENTINA'),(1915,1956302,'AUSTRALIA'),(1915,1956311,'AUSTRALIA'),(1915,1956300,'AUSTRALIA'),
 (2236,1964319,'ECUADOR'),(2878,1964310,'GUATEMALA'),(2878,1964294,'GUATEMALA'),(2878,1964300,'GUATEMALA'),
 (2878,1964296,'GUATEMALA'),(2878,1964303,'GUATEMALA'),(2203,1963974,'NORTHERN IRELAND'),(2203,1963977,'NORTHERN IRELAND')]
KEYWORDS=['DOUBLE CHANCE','DOBLE OPORTUNIDAD','DRAW NO BET','EMPATE NO ACCION','ALTERNATIVE','ALTERNATIVO','HANDICAP','HÁNDICAP','TEAM TOTAL','TOTAL POR EQUIPO','BOTH TEAMS','AMBOS EQUIPOS','WINNING MARGIN','MARGEN','GAME LINE','1ST HALF','1H','2ND HALF','2H','PLAYER','PROPS']

def c(x): return re.sub(r'\s+',' ',str(x or '').replace('\xa0',' ')).strip()

def event_constructors(body):
 out=[]
 for m in re.finditer(r'newE\s*=\s*new\s+Event\((.*?)\);',body or '',re.S):
  raw=m.group(1)
  mm=re.match(r"\s*(-?\d+)\s*,\s*(\d+)\s*,\s*'([^']*)'",raw,re.S)
  if mm: out.append({'header_id':int(mm.group(1)),'event_id':int(mm.group(2)),'title':c(mm.group(3)),'raw_head':c(raw[:700])})
 return out

def main():
 OUT.mkdir(parents=True,exist_ok=True); now=datetime.now(TZ); errors=[]; results=[]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True)
  p=b.new_page(viewport={'width':1600,'height':1800},locale='es-DO',timezone_id='America/Santo_Domingo')
  ok=False
  for a in range(3):
   try:
    p.goto(START,wait_until='commit',timeout=45000);p.wait_for_timeout(12000)
    if p.locator('#tblSH_53').count(): ok=True;break
   except Exception as e: errors.append(f'nav {a+1}: {type(e).__name__}:{e}')
  if not ok: raise RuntimeError('BOSS football menu not loaded: '+' | '.join(errors))

  for header,event,menu in TARGETS:
   rec={'header_id':header,'event_id':event,'menu':menu,'related_called':False,'network':[]}
   captured=[]
   def onr(r):
    if 'juancitosport.com.do' not in r.url or r.request.resource_type not in {'xhr','fetch'}: return
    if 'RelatedEvents' not in r.url and '_method=RefreshSelectedHeader' not in r.url: return
    try: body=r.text()
    except Exception: return
    if str(event) in body or 'RelatedEvents' in r.url:
     captured.append({'url':r.url,'status':r.status,'body':body[:500000]})
   p.on('response',onr)
   try:
    if p.evaluate("typeof RelatedEvents === 'function'"):
     rec['related_called']=True
     p.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[header,event]);p.wait_for_timeout(3500)
    else: rec['error']='RelatedEvents function unavailable'
   except Exception as e: rec['error']=f'{type(e).__name__}:{e}'
   try: p.remove_listener('response',onr)
   except Exception: pass
   body=''
   try: body=c(p.locator('body').inner_text(timeout=15000))
   except Exception as e: rec['body_error']=f'{type(e).__name__}:{e}'
   rec['body_excerpt']=body[:30000]
   rec['keyword_hits']={k:(k.lower() in body.lower()) for k in KEYWORDS}
   rec['dom_market_headers']=[]
   try:
    texts=p.locator(".eventTitle,.eventTitleText,.sEventTitle,[class*='eventTitle'],[class*='EventTitle']").evaluate_all("els=>els.map(e=>(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()).filter(Boolean)")
    rec['dom_market_headers']=list(dict.fromkeys(c(x) for x in texts if c(x)))[:100]
   except Exception: pass
   constructors=[]
   for x in captured:
    constructors.extend(event_constructors(x['body']))
   uniq={x['event_id']:x for x in constructors}
   rec['network_event_constructors']=list(uniq.values())
   rec['network_event_titles']=sorted(set(x['title'] for x in uniq.values() if x['title']))
   rec['network']= [{'url':x['url'],'status':x['status'],'bytes':len(x['body'])} for x in captured]
   results.append(rec)

  b.close()

 counts={k:sum(1 for r in results if r['keyword_hits'].get(k)) for k in KEYWORDS}
 title_counts={}
 for r in results:
  for t in r['network_event_titles']: title_counts[t]=title_counts.get(t,0)+1
 summary={
  'captured_at_local':now.isoformat(),'targets':len(TARGETS),'related_called':sum(r['related_called'] for r in results),
  'keyword_event_counts':counts,'network_title_event_counts':dict(sorted(title_counts.items(),key=lambda kv:(-kv[1],kv[0]))),
  'events_with_double_chance_literal':sum(r['keyword_hits'].get('DOUBLE CHANCE') or r['keyword_hits'].get('DOBLE OPORTUNIDAD') for r in results),
  'events_with_dnb_literal':sum(r['keyword_hits'].get('DRAW NO BET') or r['keyword_hits'].get('EMPATE NO ACCION') for r in results),
  'events_with_alternative_literal':sum(r['keyword_hits'].get('ALTERNATIVE') or r['keyword_hits'].get('ALTERNATIVO') for r in results),
  'guard':'Read-only. Calls RelatedEvents only; never clicks a bet cell or mutates coupon/account.'
 }
 (OUT/'result.json').write_text(json.dumps({'summary':summary,'events':results},ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
