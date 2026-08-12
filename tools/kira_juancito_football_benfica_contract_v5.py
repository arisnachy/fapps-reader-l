from __future__ import annotations
import json,re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_benfica_contract_v5'); TZ=ZoneInfo('America/Santo_Domingo')
EVENT=1963283; HEADER=2538; SUB='shdr2536'
def c(x): return re.sub(r'\s+',' ',str(x or '').replace('\xa0',' ')).strip()
def main():
 OUT.mkdir(parents=True,exist_ok=True); now=datetime.now(TZ); network=[]; errors=[]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True); p=b.new_page(viewport={'width':1600,'height':1800},locale='es-DO',timezone_id='America/Santo_Domingo')
  def onr(r):
   if 'juancitosport.com.do' not in r.url or r.request.resource_type not in {'xhr','fetch'}: return
   try: body=r.text()
   except Exception:return
   if str(EVENT) in body or 'RelatedEvents' in r.url or '_method=RefreshSelectedHeader' in r.url:
    network.append({'url':r.url,'status':r.status,'body':body[:300000]})
  p.on('response',onr)
  ok=False
  for a in range(3):
   try:
    p.goto(START,wait_until='commit',timeout=45000);p.wait_for_timeout(12000)
    if p.locator('#'+SUB).count(): ok=True;break
   except Exception as e: errors.append(f'nav {a+1}: {type(e).__name__}:{e}')
  if not ok: raise RuntimeError('Portugal menu not loaded: '+' | '.join(errors))
  try:p.locator('#'+SUB).click(force=True,timeout=7000);p.wait_for_timeout(3500)
  except Exception as e:errors.append(f'click Portugal: {type(e).__name__}:{e}')
  base=[]
  for pref in ('ML','PS','TT'):
   try:
    rows=p.locator(f"[id^='{pref}_{EVENT}_'],[id^='SZ{pref}_{EVENT}_']").evaluate_all("els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),cls:typeof e.className==='string'?e.className:'',row:e.closest('tr')?((e.closest('tr').innerText||e.closest('tr').textContent||'').replace(/\\s+/g,' ').trim()):''}))")
    base.extend(rows)
   except Exception as e:errors.append(f'base {pref}: {type(e).__name__}:{e}')
  related_called=False
  try:
   related_called=bool(p.evaluate("typeof RelatedEvents === 'function'"))
   if related_called:
    p.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[HEADER,EVENT]);p.wait_for_timeout(5000)
  except Exception as e:errors.append(f'RelatedEvents: {type(e).__name__}:{e}')
  body=c(p.locator('body').inner_text(timeout=30000))
  ids=p.locator('[id]').evaluate_all("els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),cls:typeof e.className==='string'?e.className:'',row:e.closest('tr')?((e.closest('tr').innerText||e.closest('tr').textContent||'').replace(/\\s+/g,' ').trim()):''})).filter(x=>x.text&&(x.id||x.row))")
  selects=[]
  try: selects=p.locator('select').evaluate_all("els=>els.map(e=>({id:e.id||'',name:e.name||'',value:e.value||'',options:Array.from(e.options||[]).map(o=>({text:(o.text||'').replace(/\\s+/g,' ').trim(),value:o.value,selected:o.selected}))}))")
  except Exception as e: errors.append(f'selects:{type(e).__name__}:{e}')
  plus=[]
  for x in ids:
   txt=c((x.get('text') or '')+' '+(x.get('row') or ''))
   if re.search(r'(^|\s)\+?1\.5(\s|$)',txt) or ('Benfica' in txt and ('spread' in txt.lower() or 'run line' in txt.lower() or 'puntos' in txt.lower())):
    plus.append(x)
  b.close()
 res={'captured_at_local':now.isoformat(),'event_id':EVENT,'header_id':HEADER,'read_only':True,'navigation_errors':errors,'related_called':related_called,'base_cells':base,'plus1_5_related_matches':plus,'selects':selects,'body_mentions_plus1_5':bool(re.search(r'(^|\s)\+?1\.5(\s|$)',body)),'body_excerpt':body[:60000],'network':network,'decision':'EXACT_HOME_PLUS1_5_OBSERVED' if plus else 'HOME_PLUS1_5_NOT_OBSERVED_IN_CAPTURE'}
 (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8'); summary={k:res[k] for k in ['captured_at_local','event_id','navigation_errors','related_called','body_mentions_plus1_5','decision']};summary['base_cells']=base;summary['plus1_5_related_matches']=plus[:20];summary['selects']=selects[:20];(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
