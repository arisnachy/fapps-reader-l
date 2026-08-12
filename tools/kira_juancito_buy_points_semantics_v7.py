from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_buy_points_semantics_v7')
TZ=ZoneInfo('America/Santo_Domingo')
TERMS=[r'BuyPoint',r'BuyPoints',r'buy point',r'buy points',r'Apuesta con puntos',r'PointBuy',r'PointBuying',r'IsEventNoFullTime',r'Pleaser']

def compact(x): return re.sub(r'\s+',' ',x or '').strip()

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True)
  p=b.new_page(locale='es-DO',timezone_id='America/Santo_Domingo')
  p.goto(START,wait_until='commit',timeout=60000); p.wait_for_timeout(12000)
  srcs=p.locator('script[src]').evaluate_all("els=>els.map(e=>e.src).filter(Boolean)")
  hits=[]
  for src in srcs:
   try:
    r=p.request.get(src,timeout=30000)
    if not r.ok: continue
    text=r.text()
   except Exception: continue
   low=text.lower()
   if not any(re.search(t,text,re.I) for t in TERMS): continue
   sh=[]
   for term in TERMS:
    for m in re.finditer(term,text,re.I):
     a=max(0,m.start()-900); z=min(len(text),m.end()+1600)
     sh.append({'term':term,'snippet':compact(text[a:z])})
     if len(sh)>=80: break
    if len(sh)>=80: break
   hits.append({'src':src,'bytes':len(text),'snippets':sh})
  body=compact(p.locator('body').inner_text())
  result={'captured_at_local':datetime.now(TZ).isoformat(),'script_count':len(srcs),'hit_scripts':hits,
          'body_has_apuesta_con_puntos':'apuesta con puntos' in body.lower(),
          'guard':'Read-only static JS inspection; no bet cell click, no coupon/account mutation.'}
  (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  summary={'captured_at_local':result['captured_at_local'],'script_count':len(srcs),'hit_script_count':len(hits),
           'hit_sources':[h['src'] for h in hits],'body_has_apuesta_con_puntos':result['body_has_apuesta_con_puntos']}
  (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps(summary,ensure_ascii=False,indent=2))
  b.close()
if __name__=='__main__': main()
