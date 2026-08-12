from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
from playwright.sync_api import sync_playwright,TimeoutError as PWTimeout
OUT=Path('artifacts/kira_juancito_nfl_direct_hdr');OUT.mkdir(parents=True,exist_ok=True)
URL='https://www.juancitosport.com.do/deportes/'
TARGETS=[('LIGA NFL',30),('NFL PRE-SEASON',3064)]
def clean(s):return re.sub(r'\s+',' ',str(s or '')).strip()
def main():
  result=[]
  with sync_playwright() as p:
    b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1600,'height':1500})
    try:page.goto(URL,wait_until='commit',timeout=30000)
    except PWTimeout:pass
    page.wait_for_timeout(6500);s=next((f for f in page.frames if 'BOSSWagering/Sportsbook' in (f.url or '')),page)
    for label,hid in TARGETS:
      before=s.evaluate('(id)=>{const e=document.getElementById("Hdr"+id),d=document.getElementById("shdr"+id);return {hdr:e?.outerHTML||null,shdr:d?.outerHTML||null}}',hid)
      click=s.evaluate(r'''(id)=>{
        const ids=['shdr'+id,'Hdr'+id];const out=[];
        for(const x of ids){const e=document.getElementById(x);if(!e){out.push({id:x,found:false});continue}try{e.scrollIntoView();e.click();out.push({id:x,found:true,clicked:true,onclick:e.getAttribute('onclick')||''});return out}catch(err){out.push({id:x,found:true,error:String(err)})}}
        return out;
      }''',hid)
      page.wait_for_timeout(3000)
      snap=s.evaluate(r'''()=>{const c=s=>(s||'').replace(/\s+/g,' ').trim();return {
        body:c(document.body?.innerText||'').slice(0,160000),
        cells:Array.from(document.querySelectorAll('[id]')).filter(e=>/^(?:SZ)?(?:ML|PS|TT)_\d+_[123]$/i.test(e.id||'')).map(e=>({id:e.id,text:c(e.innerText||e.textContent),row:c(e.closest('tr')?.innerText||''),cls:e.className||''})).slice(0,10000),
        related:Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e=>({text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''})).slice(0,3000)
      }}''')
      rows=[]
      for x in snap['cells']:
        m=re.match(r'^(?:SZ)?(ML|PS|TT)_(\d+)_([123])$',x['id'],re.I)
        if m:rows.append({**x,'market_code':m.group(1).upper(),'event_id':int(m.group(2)),'selection_code':int(m.group(3)),'actionable':'tooltip_addBet' in x.get('cls','') and 'cellCandado' not in x.get('cls','')})
      infos=s.evaluate(r'''(a)=>{const scalar=o=>{const d={};if(!o)return d;for(const k of Object.keys(o).slice(0,200)){try{const v=o[k];if(v===null||['string','number','boolean'].includes(typeof v))d[k]=v}catch(_){}}return d};return a.ids.map(id=>{let x=null;try{x=WagerSession?.SearchEventInfo?.(a.h,id)}catch(_){};return {event_id:id,found:!!x,Style:x?.Style??null,EventStyle:x?.EventStyle??null,IsEventNoFullTime:x?.IsEventNoFullTime??null,MainEventId:x?.MainEventId??null,EventTitle:x?.EventTitle??null,scalar_fields:scalar(x)}})}''',{'h':hid,'ids':sorted({x['event_id'] for x in rows})})
      result.append({'target':label,'header_id':hid,'before':before,'click':click,'body':snap['body'],'cells':rows,'related':snap['related'],'event_info':infos})
    b.close()
  summary=[]
  for r in result:
    counts={};events=set();act=0
    for x in r['cells']:counts[x['market_code']]=counts.get(x['market_code'],0)+1;events.add(x['event_id']);act+=bool(x['actionable'])
    summary.append({'target':r['target'],'header_id':r['header_id'],'events':len(events),'cells':len(r['cells']),'actionable':act,'market_counts':counts,'related_links':len(r['related']),'sample_rows':r['cells'][:40],'event_info':r['event_info'][:40],'header_html':r['before']})
  out={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'read_only':True,'summary':summary,'raw':result}
  (OUT/'result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
