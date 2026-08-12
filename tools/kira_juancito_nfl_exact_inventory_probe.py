from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
from playwright.sync_api import sync_playwright,TimeoutError as PWTimeout
OUT=Path('artifacts/kira_juancito_nfl_exact_inventory');OUT.mkdir(parents=True,exist_ok=True)
URL='https://www.juancitosport.com.do/deportes/'
TARGETS=['LIGA NFL','NFL PRE-SEASON']

def clean(v):return re.sub(r'\s+',' ',str(v or '')).strip()
def click_exact(s,label):
    q=s.get_by_text(label,exact=True);attempts=[]
    for i in range(q.count()):
        n=q.nth(i);m={'i':i}
        try:
            m.update(n.evaluate("e=>({id:e.id||'',tag:e.tagName,cls:e.className||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),onclick:e.getAttribute('onclick')||''})"));m['visible']=n.is_visible()
            if m['visible']:
                n.scroll_into_view_if_needed();n.click(force=True,timeout=5000);attempts.append({**m,'clicked':True});return True,attempts
        except Exception as e:m['error']=f'{type(e).__name__}:{e}'
        attempts.append(m)
    return False,attempts

def capture(s):
    return s.evaluate(r'''()=>{
      const c=s=>(s||'').replace(/\s+/g,' ').trim();
      const cells=Array.from(document.querySelectorAll('[id]')).filter(e=>/^(?:SZ)?(?:ML|PS|TT)_\d+_[123]$/i.test(e.id||'')).map(e=>({id:e.id||'',text:c(e.innerText||e.textContent),cls:e.className||'',row:c(e.closest('tr')?.innerText||''),title:e.getAttribute('title')||'',aria:e.getAttribute('aria-label')||''}));
      const related=Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e=>({text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''}));
      const headers=Array.from(document.querySelectorAll('tr[id^="Hdr"],div[id^="shdr"]')).map(e=>({id:e.id||'',text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''}));
      return {body:c(document.body?.innerText||'').slice(0,180000),cells:cells.slice(0,10000),related:related.slice(0,3000),headers:headers.slice(0,3000)};
    }''')

def parse_cell(x):
    cid=x['id'];m=re.match(r'^(?:SZ)?(ML|PS|TT)_(\d+)_([123])$',cid,re.I)
    if not m:return None
    return {**x,'market_code':m.group(1).upper(),'event_id':int(m.group(2)),'selection_code':int(m.group(3)),'actionable':'tooltip_addBet' in x.get('cls','') and 'cellCandado' not in x.get('cls','')}

def event_info(s,rows):
    # Search each exact cell event across observed NFL header ids. Main menu showed regular=30, preseason=3064.
    return s.evaluate(r'''(args)=>{
      const out=[];const scalar=o=>{const d={};if(!o)return d;for(const k of Object.keys(o).slice(0,200)){try{const v=o[k];if(v===null||['string','number','boolean'].includes(typeof v))d[k]=v}catch(_){}}return d};
      for(const r of args.rows){let found=null,used=null;for(const h of args.headers){try{const x=WagerSession?.SearchEventInfo?.(h,r.event_id);if(x){found=x;used=h;break}}catch(_){}}
        out.push({event_id:r.event_id,header_id:used,found:!!found,Style:found?.Style??null,EventStyle:found?.EventStyle??null,IsEventNoFullTime:found?.IsEventNoFullTime??null,MainEventId:found?.MainEventId??null,EventTitle:found?.EventTitle??null,SourceEventTemplateLabelId:found?.SourceEventTemplateLabelId??null,scalar_fields:scalar(found)});
      }return out;
    }''',{'rows':rows,'headers':[30,3064]})

def main():
  allres=[]
  with sync_playwright() as p:
    b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1600,'height':1500})
    try:page.goto(URL,wait_until='commit',timeout=30000)
    except PWTimeout:pass
    page.wait_for_timeout(6500);s=next((f for f in page.frames if 'BOSSWagering/Sportsbook' in (f.url or '')),page)
    for label in TARGETS:
        ok,attempts=click_exact(s,label);page.wait_for_timeout(2500);snap=capture(s)
        rows=[parse_cell(x) for x in snap['cells']];rows=[x for x in rows if x]
        # retain only rows visually present after target click; snapshot replacement behavior is BOSS standard.
        infos=event_info(s,rows)
        allres.append({'target':label,'clicked':ok,'click_attempts':attempts,'surface_url':s.url,'body':snap['body'],'cells':rows,'related':snap['related'],'headers':snap['headers'],'event_info':infos})
    b.close()
  summary=[]
  for r in allres:
      by={};events=set();action=0
      for x in r['cells']:
          by[x['market_code']]=by.get(x['market_code'],0)+1;events.add(x['event_id']);action+=bool(x['actionable'])
      summary.append({'target':r['target'],'clicked':r['clicked'],'events':len(events),'cells':len(r['cells']),'actionable_cells':action,'market_code_counts':by,'related_links':len(r['related']),'sample_rows':[{k:x.get(k) for k in ['id','market_code','event_id','selection_code','text','row','actionable']} for x in r['cells'][:30]],'event_info':r['event_info'][:30]})
  result={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'read_only':True,'targets':allres,'summary':summary}
  (OUT/'inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
