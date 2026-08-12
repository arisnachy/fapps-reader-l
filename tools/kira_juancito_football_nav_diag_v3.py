from __future__ import annotations
import json,re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_nav_diag_v3')
TZ=ZoneInfo('America/Santo_Domingo')
def clean(x): return re.sub(r'\s+',' ',str(x or '')).strip()

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 res={'captured_at_local':datetime.now(TZ).isoformat(),'read_only':True}
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True); p=b.new_page(viewport={'width':1600,'height':1800},locale='es-DO',timezone_id='America/Santo_Domingo')
  r=p.goto(START,wait_until='domcontentloaded',timeout=120000); p.wait_for_timeout(14000)
  res['http']=r.status if r else None;res['url']=p.url
  clicks=[];done=False
  for label in ('FÚTBOL','Fútbol','FUTBOL','Futbol','Soccer'):
   if done: break
   loc=p.get_by_text(label,exact=True)
   for i in range(loc.count()):
    try:
     n=loc.nth(i)
     if n.is_visible():
      meta=n.evaluate("e=>({tag:e.tagName,id:e.id||'',cls:typeof e.className==='string'?e.className:'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),parent:e.parentElement?{tag:e.parentElement.tagName,id:e.parentElement.id||'',cls:typeof e.parentElement.className==='string'?e.parentElement.className:'',onclick:e.parentElement.getAttribute('onclick')||''}:null})")
      n.click(force=True,timeout=6000);clicks.append(meta);p.wait_for_timeout(6000);done=True;break
    except Exception: pass
  res['soccer_clicks']=clicks
  res['body_text']=clean(p.locator('body').inner_text(timeout=30000))[:180000]
  res['short_visible_nodes']=p.locator('body *').evaluate_all(r"""els=>{const c=s=>(s||'').replace(/\s+/g,' ').trim();let out=[];for(const e of els){if(!(e.offsetWidth||e.offsetHeight||e.getClientRects().length))continue;let t=c(e.innerText||e.textContent);if(!t||t.length>90)continue;if(e.children&&Array.from(e.children).some(ch=>c(ch.innerText||ch.textContent)===t))continue;let a=e;let depth=0;while(a&&depth<5&&!a.getAttribute('onclick')&&!['A','BUTTON'].includes(a.tagName)){a=a.parentElement;depth++;}out.push({tag:e.tagName,id:e.id||'',cls:typeof e.className==='string'?e.className:'',text:t,click_tag:a?a.tagName:'',click_id:a?(a.id||''):'',click_cls:a&&typeof a.className==='string'?a.className:'',onclick:a?(a.getAttribute('onclick')||''):'',depth});if(out.length>=7000)break;}return out;}""")
  b.close()
 (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
 summary={'captured_at_local':res['captured_at_local'],'http':res['http'],'soccer_clicked':bool(res['soccer_clicks']),'body_chars':len(res['body_text']),'short_visible_nodes':len(res['short_visible_nodes'])}
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
