from __future__ import annotations
import json,re
from pathlib import Path
from playwright.sync_api import sync_playwright,TimeoutError as PWTimeout
OUT=Path('artifacts/kira_mlb_srl_eventinfo_237');OUT.mkdir(parents=True,exist_ok=True)
URL='https://www.juancitosport.com.do/deportes/'

def click_exact(s,label):
    q=s.get_by_text(label,exact=True)
    for i in range(q.count()):
        n=q.nth(i)
        try:
            if n.is_visible():n.click(force=True,timeout=5000);return True
        except Exception:pass
    return False

def main():
  with sync_playwright() as p:
    b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1440,'height':1300})
    try:page.goto(URL,wait_until='commit',timeout=30000)
    except PWTimeout:pass
    page.wait_for_timeout(6000);s=next((f for f in page.frames if 'BOSSWagering/Sportsbook' in (f.url or '')),page)
    lc=click_exact(s,'PROPUESTAS DE MLB');page.wait_for_timeout(1200);sc=click_exact(s,'PROPUESTAS DE MLB - Super Run Line');page.wait_for_timeout(2500)
    cells=s.evaluate(r'''() => Array.from(document.querySelectorAll('[id]')).filter(e=>/^PS_\d+_[12]$/i.test(e.id||'') && /\(SRL\)/i.test((e.closest('tr')?.innerText||''))).map(e=>({id:e.id,row:(e.closest('tr')?.innerText||'').replace(/\s+/g,' ').trim(),text:(e.innerText||e.textContent||'').replace(/\s+/g,' ').trim()}))''')
    eids=sorted({int(re.match(r'PS_(\d+)_',x['id']).group(1)) for x in cells})
    infos=s.evaluate(r'''(ids)=>{
      const out=[]; const scalar=o=>{const d={}; if(!o)return d; for(const k of Object.keys(o).slice(0,200)){try{const v=o[k];if(v===null||['string','number','boolean'].includes(typeof v))d[k]=v}catch(_){}} return d};
      for(const id of ids){
        let x=null,err='';
        try{if(window.WagerSession&&typeof WagerSession.SearchEventInfo==='function')x=WagerSession.SearchEventInfo(237,id)}catch(e){err=String(e)}
        out.push({event_id:id,found:!!x,error:err,Style:x?.Style??null,EventStyle:x?.EventStyle??null,IsEventNoFullTime:x?.IsEventNoFullTime??null,EventNoFullTime:x?.EventNoFullTime??null,Period:x?.Period??null,Description:x?.Description??null,scalar_fields:scalar(x)});
      }return out;
    }''',eids)
    # Also inspect direct WagerSession/header collections for 237 without serializing nested objects deeply.
    globals=s.evaluate(r'''()=>{
      const o={wager_session_exists:!!window.WagerSession,search_event_info_type:typeof window.WagerSession?.SearchEventInfo};
      try{o.wager_session_keys=Object.keys(window.WagerSession||{}).slice(0,200)}catch(_){}
      return o;
    }''')
    b.close()
  result={'league_clicked':lc,'section_clicked':sc,'srl_cells':cells,'event_ids':eids,'event_info_237':infos,'globals':globals}
  found=[x for x in infos if x['found']]
  result['decision']='EVENTINFO_237_FOUND' if found else ('SRL_ROWS_FOUND_EVENTINFO_237_EMPTY' if cells else 'SRL_ROWS_PENDING')
  (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
