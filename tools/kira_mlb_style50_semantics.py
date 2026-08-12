from __future__ import annotations
import json,re
from pathlib import Path
from playwright.sync_api import sync_playwright,TimeoutError as PWTimeout
OUT=Path('artifacts/kira_mlb_style50_semantics');OUT.mkdir(parents=True,exist_ok=True)
URL='https://www.juancitosport.com.do/deportes/'

def click_exact(s,label):
    q=s.get_by_text(label,exact=True)
    for i in range(q.count()):
        n=q.nth(i)
        try:
            if n.is_visible():n.click(force=True,timeout=5000);return True
        except Exception:pass
    return False

def scalar(o):
    d={}
    if not o:return d
    for k in list(o.keys())[:240]:
        try:
            v=o[k]
            if v is None or isinstance(v,(str,int,float,bool)):d[k]=v
        except Exception:pass
    return d

def main():
  with sync_playwright() as p:
    b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1440,'height':1300})
    try:page.goto(URL,wait_until='commit',timeout=30000)
    except PWTimeout:pass
    page.wait_for_timeout(6000);s=next((f for f in page.frames if 'BOSSWagering/Sportsbook' in (f.url or '')),page)
    click_exact(s,'PROPUESTAS DE MLB');page.wait_for_timeout(1200);click_exact(s,'PROPUESTAS DE MLB - Super Run Line');page.wait_for_timeout(2200)
    result=s.evaluate(r'''()=>{
      const c=s=>(s||'').replace(/\s+/g,' ').trim();
      const scalar=o=>{const d={};if(!o)return d;for(const k of Object.keys(o).slice(0,240)){try{const v=o[k];if(v===null||['string','number','boolean'].includes(typeof v))d[k]=v}catch(_){}}return d};
      const cells=Array.from(document.querySelectorAll('[id]')).filter(e=>/^PS_\d+_[12]$/i.test(e.id||'') && /\(SRL\)/i.test(e.closest('tr')?.innerText||''));
      const ids=[...new Set(cells.map(e=>parseInt((e.id.match(/^PS_(\d+)_/i)||[])[1],10)).filter(Number.isFinite))];
      const srl=[]; const mainIds=new Set();
      for(const id of ids){
        let x=null;try{x=WagerSession.SearchEventInfo(237,id)}catch(_){}
        if(x?.MainEventId)mainIds.add(Number(x.MainEventId));
        srl.push({event_id:id,info:scalar(x)});
      }
      const families=[];
      const ei=WagerSession?.EventInfo;
      const roots=[];
      try{
        if(Array.isArray(ei)) roots.push(...ei);
        else if(ei && typeof ei==='object') roots.push(...Object.values(ei));
      }catch(_){}
      const flat=[]; const seen=new Set();
      const walk=(v,depth=0)=>{
        if(depth>4||v==null)return;
        if(Array.isArray(v)){for(const z of v.slice(0,5000))walk(z,depth+1);return}
        if(typeof v!=='object')return;
        if(seen.has(v))return;seen.add(v);
        let id=null,mid=null;try{id=Number(v.EventId);mid=Number(v.MainEventId)}catch(_){}
        if(Number.isFinite(id)&&(mainIds.has(id)||mainIds.has(mid))){flat.push(scalar(v));}
        for(const k of Object.keys(v).slice(0,150)){try{const z=v[k];if(z&&typeof z==='object')walk(z,depth+1)}catch(_){}}
      };
      for(const r of roots.slice(0,5000))walk(r,0);
      const enumMatches=[];
      const scanEnum=(name,obj)=>{
        try{
          for(const [k,v] of Object.entries(obj||{})){
            if(/style|period|inning|full|event/i.test(k)||(/style|period|inning|full|event/i.test(String(v)))) enumMatches.push({source:name,key:k,value:(typeof v==='object'?JSON.stringify(v).slice(0,1000):v)});
          }
        }catch(_){}
      };
      scanEnum('InternalEnums',WagerSession?.InternalEnums);scanEnum('jISBEnums',WagerSession?.jISBEnums);
      const relatedDom=Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e=>({text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''}));
      return {srl,main_event_ids:[...mainIds],family_eventinfo:flat,enum_matches:enumMatches,related_dom:relatedDom};
    }''')
    # Call all observed related headers for first SRL main family, then inspect EventInfo again.
    main_ids=result.get('main_event_ids',[])
    related_headers=[]
    for x in result.get('related_dom',[]):
        m=re.search(r'RelatedEvents\((\d+),\s*(\d+),',x.get('onclick',''))
        if m: related_headers.append((int(m.group(1)),int(m.group(2)),x.get('text','')))
    probes=[]
    for h,eid,text in related_headers[:120]:
        try:
            info=s.evaluate('(a)=>{try{const x=WagerSession.SearchEventInfo(a[0],a[1]);if(!x)return null;const d={};for(const k of Object.keys(x).slice(0,240)){const v=x[k];if(v===null||["string","number","boolean"].includes(typeof v))d[k]=v}return d}catch(e){return {error:String(e)}}}',[h,eid])
            if info:probes.append({'header_id':h,'event_id':eid,'dom_text':text,'info':info})
        except Exception as exc:probes.append({'header_id':h,'event_id':eid,'dom_text':text,'error':str(exc)})
    result['direct_related_eventinfo']=probes
    b.close()
  # Summarize style/title mapping, preserving authoritative raw values.
  mappings=[]
  for x in result.get('srl',[]):
      i=x.get('info') or {};mappings.append({'source':'srl','HeaderId':i.get('HeaderId'),'EventId':i.get('EventId'),'MainEventId':i.get('MainEventId'),'EventTitle':i.get('EventTitle'),'Style':i.get('Style'),'SourceEventTemplateId':i.get('SourceEventTemplateId'),'SourceEventTemplateLabelId':i.get('SourceEventTemplateLabelId')})
  for x in result.get('direct_related_eventinfo',[]):
      i=x.get('info') or {};mappings.append({'source':'related','HeaderId':i.get('HeaderId',x.get('header_id')),'EventId':i.get('EventId',x.get('event_id')),'MainEventId':i.get('MainEventId'),'EventTitle':i.get('EventTitle') or x.get('dom_text'),'Style':i.get('Style'),'SourceEventTemplateId':i.get('SourceEventTemplateId'),'SourceEventTemplateLabelId':i.get('SourceEventTemplateLabelId')})
  result['style_title_mappings']=mappings
  (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'main_event_ids':result.get('main_event_ids'),'style_title_mappings':mappings,'enum_matches':result.get('enum_matches',[])},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
