from __future__ import annotations
import json,re,csv,io
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_league_rule_map_v9')
TZ=ZoneInfo('America/Santo_Domingo')
EVENTS=[(2538,1963283,'Benfica-Casa Pia'),(1915,1956300,'Heidelberg-North Sunshine'),(2203,1963977,'ST James-Bangor')]

def split_args(s):
    try: return next(csv.reader(io.StringIO(s),skipinitialspace=True,quotechar="'",escapechar='\\'))
    except Exception: return []

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True); p=b.new_page(locale='es-DO',timezone_id='America/Santo_Domingo')
  nav_errors=[]; loaded=False
  for attempt in range(3):
   try:
    p.goto(START,wait_until='commit',timeout=45000); p.wait_for_timeout(10000)
    if p.locator('#tblSH_53').count(): loaded=True; break
   except Exception as ex: nav_errors.append(f'attempt {attempt+1}: {type(ex).__name__}: {ex}')
  if not loaded:
   b.close(); raise RuntimeError('BOSS football menu not loaded: '+' | '.join(nav_errors))
  # Constructor signature from static scripts.
  sigs=[]
  srcs=p.locator('script[src]').evaluate_all("els=>els.map(e=>e.src).filter(Boolean)")
  for src in srcs:
   try:
    r=p.request.get(src,timeout=30000); text=r.text() if r.ok else ''
   except Exception: continue
   for pat in [r'function\s+Event\s*\(([^)]{1,2000})\)',r'Event\s*=\s*function\s*\(([^)]{1,2000})\)']:
    for m in re.finditer(pat,text): sigs.append({'src':src,'signature':m.group(1),'snippet':re.sub(r'\s+',' ',text[max(0,m.start()-200):min(len(text),m.end()+5000)])})
  recs=[]
  for h,e,label in EVENTS:
   caps=[]
   def onr(r):
    if 'juancitosport.com.do' not in r.url or r.request.resource_type not in {'xhr','fetch'}: return
    try: txt=r.text()
    except Exception: return
    if str(e) in txt and ('new Event(' in txt or 'newEvent' in txt or 'newE' in txt): caps.append({'url':r.url,'status':r.status,'text':txt[:1000000]})
   p.on('response',onr)
   try:
    p.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[h,e]);p.wait_for_timeout(4000)
   finally:
    try:p.remove_listener('response',onr)
    except Exception:pass
   ct=[]
   for cap in caps:
    txt=cap['text']
    for m in re.finditer(r'new\s+Event\s*\((.*?)\)\s*;',txt,re.S):
     raw=m.group(1); args=split_args(raw)
     if any(str(e)==a.strip() for a in args[:6]): ct.append({'url':cap['url'],'raw':re.sub(r'\s+',' ',raw)[:12000],'args':args[:80]})
   recs.append({'event_id':e,'label':label,'captures':len(caps),'constructors':ct})
  globals_map={}
  for _,e,_ in EVENTS:
   try:
    globals_map[str(e)]=p.evaluate("""(eid)=>{
      const out=[];
      function scal(o){let z={}; if(!o||typeof o!=='object')return z; for(const k of Object.keys(o).slice(0,120)){try{const v=o[k]; if(v===null||['string','number','boolean'].includes(typeof v))z[k]=v;}catch(e){}} return z;}
      for(const k of Object.keys(window)){
        let v; try{v=window[k]}catch(e){continue}; if(!v||typeof v!=='object')continue;
        try{
          const s=scal(v); if(Object.values(s).some(x=>String(x)===String(eid))) out.push({path:k,scalars:s});
          if(Array.isArray(v)) for(let i=0;i<Math.min(v.length,2000);i++){const q=v[i]; const ss=scal(q); if(Object.values(ss).some(x=>String(x)===String(eid))) out.push({path:`${k}[${i}]`,scalars:ss});}
          else for(const kk of Object.keys(v).slice(0,500)){const q=v[kk]; if(q&&typeof q==='object'){const ss=scal(q); if(Object.values(ss).some(x=>String(x)===String(eid))) out.push({path:`${k}.${kk}`,scalars:ss});}}
        }catch(e){}
        if(out.length>=80)break;
      }
      return out;
    }""",e)
   except Exception as ex: globals_map[str(e)]={'error':str(ex)}
  result={'captured_at_local':datetime.now(TZ).isoformat(),'nav_errors':nav_errors,'constructor_signatures':sigs[:20],'events':recs,'globals':globals_map,'guard':'Read-only event/network/global inspection; no bet selection or coupon/account mutation.'}
  (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  summ={'captured_at_local':result['captured_at_local'],'nav_errors':nav_errors,'signature_count':len(sigs),'events':[{'event_id':x['event_id'],'constructors':len(x['constructors']),'captures':x['captures']} for x in recs],'global_hits':{k:len(v) if isinstance(v,list) else 0 for k,v in globals_map.items()}}
  (OUT/'summary.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summ,ensure_ascii=False,indent=2));b.close()
if __name__=='__main__':main()
