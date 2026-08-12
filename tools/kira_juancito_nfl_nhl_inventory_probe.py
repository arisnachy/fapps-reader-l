from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
from playwright.sync_api import sync_playwright,TimeoutError as PWTimeout
OUT=Path('artifacts/kira_juancito_nfl_nhl_inventory');OUT.mkdir(parents=True,exist_ok=True)
URL='https://www.juancitosport.com.do/deportes/'
TERMS=re.compile(r'NFL|FOOTBALL|FUTBOL AMERICANO|FÚTBOL AMERICANO|NHL|HOCKEY|PRETEMPORADA|PRESEASON',re.I)
def main():
  with sync_playwright() as p:
    b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1600,'height':1600})
    try:page.goto(URL,wait_until='commit',timeout=30000)
    except PWTimeout:pass
    page.wait_for_timeout(7000);s=next((f for f in page.frames if 'BOSSWagering/Sportsbook' in (f.url or '')),page)
    data=s.evaluate(r'''()=>{
      const c=s=>(s||'').replace(/\s+/g,' ').trim();
      const all=Array.from(document.querySelectorAll('a,button,div,span,li,tr,td')).map((e,i)=>({i,tag:e.tagName,id:e.id||'',cls:e.className||'',text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||'',title:e.getAttribute('title')||''})).filter(x=>x.text);
      const cells=Array.from(document.querySelectorAll('[id]')).filter(e=>/^(SZ)?(ML|PS|TT)_\d+_/i.test(e.id||'')).map(e=>({id:e.id,text:c(e.innerText||e.textContent),row:c(e.closest('tr')?.innerText||''),cls:e.className||''}));
      return {body:c(document.body?.innerText||'').slice(0,250000),elements:all.slice(0,20000),cells:cells.slice(0,10000)};
    }''')
    b.close()
  matches=[x for x in data['elements'] if TERMS.search(x.get('text','')) or TERMS.search(x.get('onclick','')) or TERMS.search(x.get('title',''))]
  # Deduplicate text/onclick signatures while preserving exact public labels.
  seen=set();uniq=[]
  for x in matches:
    k=(x.get('text'),x.get('onclick'),x.get('id'))
    if k in seen:continue
    seen.add(k);uniq.append(x)
  related_cells=[x for x in data['cells'] if TERMS.search(x.get('row',''))]
  res={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'surface_url':getattr(s,'url','') if False else None,'term_matches':uniq[:1000],'matching_market_cells':related_cells[:3000],'body_term_lines':[ln for ln in data['body'].split(' | ') if TERMS.search(ln)][:1000],'counts':{'term_matches':len(uniq),'matching_cells':len(related_cells)}}
  (OUT/'inventory.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
