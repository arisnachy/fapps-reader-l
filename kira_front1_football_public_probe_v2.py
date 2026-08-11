from __future__ import annotations

import json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from playwright.sync_api import sync_playwright

OUT=Path('front1_football_contract_inventory_v2'); OUT.mkdir(parents=True,exist_ok=True)
START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
LEAGUES=['USA','SPAIN','AUSTRIA','GERMANY','ITALY','FRANCE','PORTUGAL','NETHERLANDS','SCOTLAND','BELGIUM']
TERMS={
'double_chance':re.compile(r'(?i)double\s+chance|doble\s+oportunidad'),
'draw_no_bet':re.compile(r'(?i)draw\s+no\s+bet|empate\s+(?:no\s+)?apuesta|sin\s+empate'),
'team_total':re.compile(r'(?i)team\s+total|total\s+(?:del|por|solo\s+por)\s+equipo'),
'winning_margin':re.compile(r'(?i)winning\s+margin|margen\s+de\s+victoria'),
'handicap':re.compile(r'(?i)handicap|hándicap'),
}

def now(): return datetime.now(timezone.utc).isoformat()
def clean(x): return re.sub(r'\s+',' ',str(x or '').replace('\xa0',' ')).strip()
def redact_text(t):
 t=str(t or ''); t=re.sub(r'(?i)(stoken|_session|session|token)=([^&\'"\\\s]+)',r'\1=REDACTED',t); t=re.sub(r'(?i)(SessionID\s*[=:]\s*[\'"])[^\'"]+',r'\1REDACTED',t); t=re.sub(r'(?i)(PlayerInfo\s*[=:]\s*[\'"])[A-Za-z0-9+/=_-]{20,}',r'\1REDACTED',t); return t
def redact_url(url):
 try:
  p=urlsplit(url); q=[]
  for k,v in parse_qsl(p.query,keep_blank_values=True):
   if k.casefold() in {'stoken','_session','session','token'}: v='REDACTED'
   q.append((k,v))
  return urlunsplit((p.scheme,p.netloc,p.path,urlencode(q),p.fragment))
 except Exception:return url
def same_site(url):
 try:return (urlsplit(url).hostname or '').endswith('juancitosport.com.do')
 except Exception:return False

def parse_xhr_events(body):
 out=[]
 # Support both exact historical PR65 form and looser Event(...) form.
 for payload in re.findall(r'new\s+Event\((.*?)\)',body or '',re.S):
  nums=re.match(r'\s*(-?\d+)\s*,\s*(\d+)\s*,',payload)
  if not nums: continue
  h,e=int(nums.group(1)),int(nums.group(2)); sport=''
  for s in ('Soccer','Basketball','Tennis','Baseball'):
   if f"'{s}'" in payload or f'"{s}"' in payload: sport=s; break
  title=''
  tm=re.match(r"\s*-?\d+\s*,\s*\d+\s*,\s*'((?:\\'|[^'])*)'",payload)
  if tm:title=tm.group(1).replace("\\'", "'")
  out.append({'header_id':h,'event_id':e,'sport':sport,'title':title,'source':'xhr'})
 return out

def related_links(page):
 try:
  vals=page.locator("a[onclick*='RelatedEvents']").evaluate_all("els=>els.map(e=>({text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),onclick:e.getAttribute('onclick')||''}))")
 except Exception:return []
 out=[]
 for x in vals:
  m=re.search(r'RelatedEvents\((\d+)\s*,\s*(\d+)',x.get('onclick',''))
  if m: out.append({'header_id':int(m.group(1)),'event_id':int(m.group(2)),'title':clean(x.get('text')),'source':'dom_related'})
 return out

def click_exact(page,label):
 loc=page.get_by_text(label,exact=True)
 for i in range(loc.count()):
  try:
   n=loc.nth(i)
   if n.is_visible(): n.scroll_into_view_if_needed(timeout=3000); n.click(timeout=6000,force=True); return True
  except Exception: pass
 return False

def call_related(page,h,e):
 try:
  if not page.evaluate("typeof RelatedEvents === 'function'"): return False,'RelatedEvents_not_available'
  page.evaluate('([h,e])=>RelatedEvents(h,e,1,0)',[h,e]); page.wait_for_timeout(3000); return True,None
 except Exception as exc:return False,f'{type(exc).__name__}: {exc}'

def market_actions(page,event):
 if page.locator('#dvBetZone').count()==0:return []
 data=page.locator('#dvBetZone tr').evaluate_all(r"""rows=>{const c=s=>(s||'').replace(/\s+/g,' ').trim(); const sec=el=>{let n=el;while(n&&n.id!=='dvBetZone'&&n!==document.body){let p=n.previousElementSibling;while(p){if(p.matches&&p.matches('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]')){let t=c(p.innerText||p.textContent);if(t)return t;}if(p.querySelectorAll){let hs=p.querySelectorAll('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]');if(hs.length){let t=c(hs[hs.length-1].innerText||hs[hs.length-1].textContent);if(t)return t;}}p=p.previousElementSibling;}n=n.parentElement;}return '';};return rows.map(r=>{let pn=r.querySelector('.colParticipantInfoParticipant,.SchUpcomingParticipant,.upcomingParticipantName');let participant=pn?c(pn.innerText||pn.textContent):'';return {section:sec(r),row_text:c(r.innerText||r.textContent),actions:Array.from(r.querySelectorAll('a,button,[onclick],.tooltip_addBet')).map(a=>({text:c(a.innerText||a.textContent),id:a.id||'',class_name:typeof a.className==='string'?a.className:'',title:a.getAttribute('title')||'',aria:a.getAttribute('aria-label')||'',participant,actionable:a.classList?a.classList.contains('tooltip_addBet'):false,locked:a.classList?a.classList.contains('cellCandado'):false}))};});}""")
 out=[]
 for row in data:
  for a in row.get('actions') or []:
   out.append({'captured_at_utc':now(),'header_id':event['header_id'],'event_id':event['event_id'],'event_title':event.get('title',''),'source_league':event.get('source_league',''),'section_title':clean(row.get('section')),'participant_name':clean(a.get('participant')),'action_text':clean(a.get('text')),'action_id':clean(a.get('id')),'action_class':clean(a.get('class_name')),'title':clean(a.get('title')),'aria_label':clean(a.get('aria')),'row_text':clean(row.get('row_text')),'actionable':bool(a.get('actionable')),'locked':bool(a.get('locked'))})
 return out

def main():
 network=[]; structural=[]; xhr_events={}; league_clicks=[]; candidates={}; actions=[]; snapshots=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True); ctx=browser.new_context(viewport={'width':1440,'height':1400},locale='es-DO',timezone_id='America/Santo_Domingo'); page=ctx.new_page()
  def response(resp):
   req=resp.request
   if not same_site(resp.url) or req.resource_type not in {'xhr','fetch'}: return
   rec={'url':redact_url(resp.url),'status':resp.status,'method':req.method,'captured_at_utc':now()}
   try:
    body=redact_text(resp.text()); evs=parse_xhr_events(body)
    for ev in evs:xhr_events[(ev['header_id'],ev['event_id'])]=ev
    if '_method=GetUpcomingEvents' in resp.url or '_method=RefreshSelectedHeader' in resp.url:
     structural.append({'url':redact_url(resp.url),'preview':body[:12000],'event_parser_hits':len(evs)})
   except Exception as exc:rec['body_error']=f'{type(exc).__name__}: {exc}'
   network.append(rec)
  page.on('response',response)
  nav={'captured_at_utc':now(),'start_url':START}
  try:r=page.goto(START,wait_until='domcontentloaded',timeout=120000); nav['status']=r.status if r else None
  except Exception as exc:nav['error']=f'{type(exc).__name__}: {exc}'
  page.wait_for_timeout(14000); nav['final_url']=redact_url(page.url)
  for label in LEAGUES:
   clicked=click_exact(page,label); league_clicks.append({'label':label,'clicked':clicked})
   if clicked:
    page.wait_for_timeout(2200)
    links=related_links(page)
    for ev in links:
     ev['sport']='Soccer'; ev['source_league']=label; candidates[(ev['header_id'],ev['event_id'])]=ev
  page.wait_for_timeout(2500)
  for k,ev in xhr_events.items():
   if ev.get('sport')=='Soccer' and k not in candidates: candidates[k]={**ev,'source_league':'xhr'}
  chosen=list(candidates.values())[:16]; details=[]
  for ev in chosen:
   ok,err=call_related(page,ev['header_id'],ev['event_id']); details.append({**ev,'related_called':ok,'error':err})
   if not ok:continue
   try:body=redact_text(page.locator('body').inner_text(timeout=20000))[:150000]
   except Exception:body=''
   snapshots.append({'event':ev,'body':body}); actions.extend(market_actions(page,ev))
  ctx.close();browser.close()
 term_hits={k:[] for k in TERMS}; corp=[]
 for s in snapshots:corp.append((f"snapshot:{s['event']['event_id']}",s['body']))
 for s in structural:corp.append(('xhr_structural',s.get('preview','')))
 for a in actions:corp.append((f"action:{a['event_id']}:{a['action_id']}",json.dumps(a,ensure_ascii=False)))
 for src,text in corp:
  for name,rx in TERMS.items():
   for m in rx.finditer(text or ''):
    term_hits[name].append({'source':src,'snippet':clean(text[max(0,m.start()-200):min(len(text),m.end()+320)])})
    if len(term_hits[name])>=60:break
 dc=[]
 for a in actions:
  text=' '.join(str(a.get(k) or '') for k in ('section_title','participant_name','action_text','row_text','title','aria_label'))
  if TERMS['double_chance'].search(text):dc.append(a)
 summary={'captured_at_utc':now(),'execution':'anonymous_public_read_only','transport':'standalone mirror of PR65 public BOSS + DOM RelatedEvents mechanics','navigation':nav,'league_clicks':league_clicks,'xhr_event_refs_seen':len(xhr_events),'dom_or_xhr_soccer_candidates':len(candidates),'soccer_events_examined':sum(1 for d in details if d['related_called']),'details':details,'market_action_rows':len(actions),'actionable_rows':sum(1 for a in actions if a['actionable']),'double_chance_action_rows':len(dc),'term_hit_counts':{k:len(v) for k,v in term_hits.items()},'coverage_complete':False,'guard':'Discovery only. Missing families cannot be declared unavailable because coverage_complete=false. No scoring or settlement inference.'}
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8'); (OUT/'term_hits.json').write_text(json.dumps(term_hits,indent=2,ensure_ascii=False),encoding='utf-8'); (OUT/'football_market_actions.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in actions)+('\n' if actions else ''),encoding='utf-8'); (OUT/'double_chance_actions.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in dc)+('\n' if dc else ''),encoding='utf-8'); (OUT/'network_structural.json').write_text(json.dumps(structural,indent=2,ensure_ascii=False),encoding='utf-8'); (OUT/'network_meta.json').write_text(json.dumps(network,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(summary,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
