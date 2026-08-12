from __future__ import annotations
import hashlib,json,re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_tierb_event_surface_v18')
TZ=ZoneInfo('America/Santo_Domingo')
TARGETS=[
 (2037,1961877,'Shandong Luneng Taishan','CHINA',1),
 (2015,1962330,'Ruch Chorzow','POLAND',2),
 (2059,1959023,'LASK Linz','AUSTRIA',3),
]
SAFE=('más','mas','more','more markets','más mercados','mas mercados','advanced player and game props','advanced props','player and game props','propuestas avanzadas','propuestas de jugador','otros mercados')
BET_RE=re.compile(r'^(?:u)?(?:PS|ML|TT|TTT)_(\d+)_\d+$',re.I)
NUM_RE=re.compile(r'[-+]?\d+(?:[.,]\d+)?')

def c(x): return re.sub(r'\s+',' ',str(x or '').replace('\xa0',' ')).strip()
def h(x): return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def redact(s):
 s=str(s or '')
 s=re.sub(r'(?i)(token|authorization|auth|jwt|key|session|cookie)=([^&\s]+)',r'\1=[REDACTED]',s)
 s=re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~+\-/=]+',r'\1[REDACTED]',s)
 return s[:1200]

def scan(page, team):
 zone=page.locator('#dvBetZone')
 if not zone.count(): return {'expanders':[],'selects':[],'surface':{},'exact_rows':[],'bet_event_ids':[]}
 data=zone.evaluate("""(z)=>{
 const clean=s=>(s||'').replace(/\s+/g,' ').trim();
 const section=el=>{let n=el;while(n&&n!==z&&n!==document.body){let p=n.previousElementSibling;while(p){if(p.matches&&p.matches('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]')){const t=clean(p.innerText||p.textContent);if(t)return t;}p=p.previousElementSibling;}n=n.parentElement;}return ''};
 const nodes=[...z.querySelectorAll('a,button,[onclick]')].map((e,index)=>{const tr=e.closest('tr');return {index,id:e.id||'',cls:typeof e.className==='string'?e.className:'',text:clean(e.innerText||e.textContent),title:e.getAttribute('title')||'',section:section(e),row:tr?clean(tr.innerText||tr.textContent):''}});
 const sels=[...z.querySelectorAll('select')].map((e,index)=>{const tr=e.closest('tr');let p=tr?tr.querySelector('.colParticipantInfoParticipant,.SchUpcomingParticipant,.upcomingParticipantName'):null;return {index,id:e.id||'',name:e.name||'',section:section(e),participant:p?clean(p.innerText||p.textContent):'',row:tr?clean(tr.innerText||tr.textContent):'',options:[...e.options].map(o=>({text:clean(o.textContent),value:o.value,disabled:o.disabled,selected:o.selected}))}});
 const rows=[...z.querySelectorAll('tr')].map((tr,index)=>({index,text:clean(tr.innerText||tr.textContent),html:tr.outerHTML.slice(0,15000),actions:[...tr.querySelectorAll('[id]')].map(x=>({id:x.id||'',cls:typeof x.className==='string'?x.className:'',text:clean(x.innerText||x.textContent)}))}));
 const frames=[...z.querySelectorAll('iframe')].map(f=>{try{let u=new URL(f.src,location.href);return {host:u.host,path:u.pathname};}catch(e){return {host:'',path:''}}});
 return {nodes,sels,rows,frames};
 }""")
 exp=[]
 for n in data['nodes']:
  nid=c(n['id']); cls=c(n['cls']).lower(); text=c(n['text']).lower(); title=c(n['title']).lower()
  if BET_RE.match(nid) or 'tooltip_addbet' in cls or 'cellcandado' in cls: continue
  if any(m==text or m in text or m in title for m in SAFE):
   n['key']=h([nid,c(n['section']).lower(),c(n['row']).lower()[:300],text,title])[:24];exp.append(n)
 sels=[]
 for s in data['sels']:
  sk=h([c(s['id']),c(s['name']),c(s['participant']).lower(),c(s['section']).lower(),c(s['row']).lower()[:250]])[:24]
  opts=[]
  for o in s['options']:
   if o.get('disabled') or not NUM_RE.search(c(o.get('text'))): continue
   oo=dict(o);oo['key']=h([sk,c(o.get('value')),c(o.get('text'))])[:24];opts.append(oo)
  if opts:
   ss=dict(s);ss['key']=sk;ss['numeric_options']=opts;sels.append(ss)
 exact=[]; betids=set()
 t=team.lower()
 for r in data['rows']:
  text=c(r['text']); low=text.lower(); acts=[]
  for a in r['actions']:
   m=BET_RE.match(c(a['id']))
   if m: betids.add(int(m.group(1)))
   if 'tooltip_addbet' in c(a['cls']).lower() and 'cellcandado' not in c(a['cls']).lower(): acts.append(a)
  has15=('+1.5' in low or '+1½' in low or re.search(r'(?<!\d)\+?1\.5(?!\d)',low) is not None)
  if t in low and has15:
   exact.append({'text':text[:1200],'actions':acts[:20]})
 surf={'rows':[c(r['text']) for r in data['rows']],'nodes':[{'id':c(n['id']),'cls':c(n['cls']),'text':c(n['text']),'title':c(n['title'])} for n in data['nodes']], 'selects':[{'id':c(s['id']),'name':c(s['name']),'participant':c(s['participant']),'section':c(s['section']),'options':[(c(o['text']),c(o['value']),bool(o['disabled'])) for o in s['options']]} for s in data['sels']], 'frames':data['frames']}
 return {'expanders':exp,'selects':sels,'surface':surf,'surface_hash':h(surf),'exact_rows':exact,'bet_event_ids':sorted(betids)}

def click_expander(page,node):
 if c(node.get('id')):
  ok=page.evaluate("id=>{const e=document.getElementById(id);if(!e)return false;e.click();return true}",c(node['id']))
  if not ok: raise RuntimeError('expander id vanished')
 else:
  loc=page.locator('#dvBetZone').locator('a,button,[onclick]').nth(int(node['index']));loc.click(force=True,timeout=3500)
 page.wait_for_timeout(650)

def choose_option(page,sel,opt):
 idx=None
 if c(sel.get('id')):
  q=page.locator('#dvBetZone select').evaluate_all("(els,id)=>els.map((e,i)=>({i,id:e.id||''})).filter(x=>x.id===id)",c(sel['id']))
  if len(q)==1: idx=q[0]['i']
 if idx is None:
  cur=page.locator('#dvBetZone select').evaluate_all("els=>els.map((e,i)=>({i,id:e.id||'',name:e.name||'',row:(e.closest('tr')?.innerText||'').replace(/\\s+/g,' ').trim()}))")
  matches=[x for x in cur if c(x['name'])==c(sel.get('name')) and c(sel.get('row'))[:120] in c(x['row'])]
  if len(matches)==1: idx=matches[0]['i']
 if idx is None: raise RuntimeError('select identity unresolved')
 loc=page.locator('#dvBetZone select').nth(idx)
 val=c(opt.get('value')); txt=c(opt.get('text'))
 if val: loc.select_option(value=val,timeout=4000)
 else: loc.select_option(label=txt,timeout=4000)
 page.wait_for_timeout(700)

def certify(page,hid,eid,team,country,rank):
 try:
  page.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[hid,eid]);page.wait_for_timeout(3000)
 except Exception as ex:
  return {'header_id':hid,'event_id':eid,'team':team,'country':country,'rank':rank,'status':'MARKET_DATA_PENDING','event_surface_complete':False,'reason':'RELATED_EVENTS_FAILED','error':f'{type(ex).__name__}:{ex}'}
 attempted_e=set();attempted_o=set();errors=[];stable=[];obs=[];interactions=0;final=None
 while interactions<350:
  s=scan(page,team);final=s
  if s['exact_rows']: obs.extend(s['exact_rows'])
  nxt=next((x for x in s['expanders'] if x['key'] not in attempted_e),None)
  if nxt:
   attempted_e.add(nxt['key'])
   try:click_expander(page,nxt)
   except Exception as ex:errors.append({'kind':'expander','key':nxt['key'],'error':f'{type(ex).__name__}:{ex}'})
   interactions+=1;stable=[];continue
  pair=None
  for sel in s['selects']:
   for o in sel['numeric_options']:
    if o['key'] not in attempted_o: pair=(sel,o);break
   if pair:break
  if pair:
   sel,o=pair;attempted_o.add(o['key'])
   try:choose_option(page,sel,o)
   except Exception as ex:errors.append({'kind':'select','key':o['key'],'error':f'{type(ex).__name__}:{ex}'})
   interactions+=1;stable=[];continue
  stable.append(s['surface_hash']);stable=stable[-3:]
  if len(stable)==3 and len(set(stable))==1:break
  page.wait_for_timeout(800)
 s=scan(page,team);final=s
 wrong=[x for x in s['bet_event_ids'] if x!=eid]
 unresolved_e=[x for x in s['expanders'] if x['key'] not in attempted_e]
 unresolved_o=[o for sel in s['selects'] for o in sel['numeric_options'] if o['key'] not in attempted_o]
 complete=bool(len(stable)==3 and len(set(stable))==1 and not errors and not wrong and not unresolved_e and not unresolved_o and interactions<350)
 uniq=[];seen=set()
 for x in obs+s['exact_rows']:
  k=h(x)
  if k not in seen:seen.add(k);uniq.append(x)
 actionable_exact=any(any('tooltip_addBet' in c(a.get('cls')) and 'cellCandado' not in c(a.get('cls')) and (BET_RE.match(c(a.get('id'))) and int(BET_RE.match(c(a.get('id'))).group(1))==eid) for a in r.get('actions',[])) for r in uniq)
 status='PUBLIC_MARKET_PRESENT' if actionable_exact else ('PUBLIC_MARKET_UNAVAILABLE_AFTER_FIXED_POINT' if complete else 'MARKET_DATA_PENDING')
 return {'header_id':hid,'event_id':eid,'team':team,'country':country,'rank':rank,'event_surface_complete':complete,'status':status,'selected_plus1_5_actionable_observed':actionable_exact,'exact_rows':uniq[:30],'interactions':interactions,'stable_hashes':stable,'safe_expanders_attempted':len(attempted_e),'numeric_options_attempted':len(attempted_o),'interaction_errors':errors,'wrong_bet_event_ids':wrong,'bet_event_ids':s['bet_event_ids'],'surface_hash':s['surface_hash'],'guard':'PUBLIC surface only; does not certify authenticated/Advanced Props surface.'}

def main():
 OUT.mkdir(parents=True,exist_ok=True);nav=[];results=[]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':1800,'height':2200},locale='es-DO',timezone_id='America/Santo_Domingo')
  loaded=False
  for a in range(5):
   try:
    p.goto(START,wait_until='commit',timeout=45000);p.wait_for_timeout(9000)
    if p.locator('#tblSH_53').count():loaded=True;break
   except Exception as ex:nav.append(f'{a+1}:{type(ex).__name__}:{ex}')
   p.wait_for_timeout(2000)
  if not loaded:b.close();raise RuntimeError('BOSS unavailable: '+' | '.join(nav))
  for x in TARGETS:results.append(certify(p,*x))
  b.close()
 res={'captured_at_local':datetime.now(TZ).isoformat(),'nav_errors':nav,'results':results,'guard':'Read-only public event-surface fixed-point probe. Never clicks wager cells; never mutates coupon/account/stake. Public certificate is explicitly non-global.'}
 (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
 summ={'captured_at_local':res['captured_at_local'],'results':[{k:r.get(k) for k in ['rank','event_id','team','event_surface_complete','status','selected_plus1_5_actionable_observed','interactions','safe_expanders_attempted','numeric_options_attempted','wrong_bet_event_ids']} for r in results]}
 (OUT/'summary.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summ,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
