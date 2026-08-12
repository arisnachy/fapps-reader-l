from __future__ import annotations

import ast
import hashlib
import html
import json
import re
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from playwright.sync_api import Page, sync_playwright

START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_dual_catalog_graph_v20')
TZ=ZoneInfo('America/Santo_Domingo')
BET_CELL_RE=re.compile(r'^(?:u)?(?:PS|ML|TT|TTT)_\d+_\d+$',re.I)
RELATED_RE=re.compile(r'RelatedEvents\((\d+)\s*,\s*(\d+)',re.I)
DANGEROUS_RE=re.compile(r'(?i)(crear cup[oó]n|place\s*bet|submit\s*bet|confirm\s*bet|apostar|realizar apuesta|monto|stake|deposit|dep[oó]sito|retirar|withdraw|cajero|cashier|mi cuenta|logout|salir)')
BOARD_SAFE_RE=re.compile(r'(?i)(sport|deporte|league|liga|upcoming|próxim|proxim|today|hoy|tomorrow|mañana|manana|soccer|f[uú]tbol|football|basket|baseball|b[eé]isbol|tennis|tenis|wnba|nba|mlb|nfl|nhl|props?|propuestas?|game lines|l[ií]neas de juego|header|shdr)')
ACCOUNT_RE=re.compile(r'(?i)(account|cuenta|balance|idioma|language|moneda|currency|timezone|zona horaria)')
AMERICAN_PRICE_RE=re.compile(r'(?<![\d.])[+-](?:1\d\d|[2-9]\d\d|\d{4,})(?![\d.])')


def clean(v:Any)->str:return re.sub(r'\s+',' ',str(v or '')).strip()
def strip_price(v:Any)->str:return clean(AMERICAN_PRICE_RE.sub('<PRICE>',clean(v)))
def digest(v:Any)->str:return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
def redact_url(url:str)->str:
    try:
        from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
        p=urlsplit(str(url or '')); safe=[]
        for k,v in parse_qsl(p.query,keep_blank_values=True):
            if re.search(r'(?i)(token|jwt|auth|session|cookie|key|challenge)',k):v='[REDACTED]'
            safe.append((k,v))
        return urlunsplit((p.scheme,p.netloc,p.path,urlencode(safe),''))
    except Exception:return str(url or '').split('#',1)[0]

def same_site(url:str)->bool:return 'juancitosport.com.do' in str(url or '').casefold()

def decode_boss_payload(body:str)->str:
    text=str(body or ''); s=text.strip()
    if len(s)>=2 and s[0] in {'\'', '"'} and s[-1]==s[0]:
        try:
            val=ast.literal_eval(s)
            if isinstance(val,str):return val
        except Exception:pass
    return html.unescape(text)

def split_js_args(payload:str)->list[str]:
    out=[];buf=[];quote='';esc=False;depth=0
    for ch in payload:
        if esc:buf.append(ch);esc=False;continue
        if ch=='\\':buf.append(ch);esc=True;continue
        if quote:
            buf.append(ch)
            if ch==quote:quote=''
            continue
        if ch in {'\'', '"'}:quote=ch;buf.append(ch);continue
        if ch in '([{':depth+=1
        elif ch in ')]}':depth=max(0,depth-1)
        if ch==',' and depth==0:out.append(''.join(buf).strip());buf=[]
        else:buf.append(ch)
    out.append(''.join(buf).strip());return out

def unquote(v:Any)->str:
    s=clean(v)
    if len(s)>=2 and s[0] in {'\'', '"'} and s[-1]==s[0]:
        try:return str(ast.literal_eval(s))
        except Exception:return s[1:-1].replace("\\'", "'").replace('\\"','"')
    return s

def extract_events(body:str)->list[dict[str,Any]]:
    s=decode_boss_payload(body);out={}
    for m in re.finditer(r'newE\s*=\s*new\s+Event\((.*?)\);',s,re.S):
        args=split_js_args(m.group(1))
        if len(args)<2:continue
        try:hid,eid=int(float(args[0])),int(float(args[1]))
        except Exception:continue
        style=None
        try:style=int(float(args[13])) if len(args)>13 else None
        except Exception:pass
        sport=unquote(args[37]) if len(args)>=38 else ''
        title=unquote(args[2]) if len(args)>=3 else ''
        out[(hid,eid)]={'header_id':hid,'event_id':eid,'sport':sport or 'Unknown','title':title,'event_style':style}
    return list(out.values())
def xhr_method(url:str)->str:
    m=re.search(r'[?&]_method=([^&]+)',str(url or ''),re.I);return m.group(1) if m else ''

def board_controls(page:Page)->list[dict[str,Any]]:
    try:rows=page.locator("a,button,[role='tab'],[role='button'],[onclick],summary").evaluate_all("""els=>els.map((e,index)=>{const c=s=>(s||'').replace(/\\s+/g,' ').trim();const box=e.closest('li,tr,nav,[class*=sport],[class*=league],[class*=header],[class*=event],section,article')||e.parentElement;return {index,id:e.id||'',class_name:typeof e.className==='string'?e.className:'',role:e.getAttribute('role')||'',text:c(e.innerText||e.textContent).slice(0,500),title:e.getAttribute('title')||'',aria_label:e.getAttribute('aria-label')||'',aria_expanded:e.getAttribute('aria-expanded')||'',onclick:e.getAttribute('onclick')||'',context:box?c(box.innerText||box.textContent).slice(0,1200):''}})""")
    except Exception:return []
    for r in rows:
        nid=clean(r.get('id'));cls=clean(r.get('class_name'));joined=' '.join(clean(r.get(k)) for k in ('id','class_name','role','text','title','aria_label','context','onclick'))
        direct=' '.join(clean(r.get(k)) for k in ('id','text','title','aria_label','onclick'))
        if BET_CELL_RE.match(nid) or 'tooltip_addbet' in cls.casefold() or 'cellcandado' in cls.casefold():typ='BLOCKED_WAGER_CELL'
        elif DANGEROUS_RE.search(joined) or ACCOUNT_RE.search(joined):typ='BLOCKED_MUTATION_OR_ACCOUNT'
        elif nid.casefold().startswith('shdr') or RELATED_RE.search(clean(r.get('onclick'))):typ='SAFE_BOARD_NAV'
        elif clean(r.get('role')).casefold()=='tab' or clean(r.get('aria_expanded')) in {'true','false'}:typ='SAFE_BOARD_NAV' if BOARD_SAFE_RE.search(joined) else 'IGNORE_NON_BOARD'
        elif BOARD_SAFE_RE.search(direct):typ='SAFE_BOARD_NAV'
        else:typ='IGNORE_NON_BOARD'
        r['classification']=typ
    return rows

def board_selects(page:Page)->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    try:rows=page.locator('select').evaluate_all("""els=>els.map((e,index)=>{const c=s=>(s||'').replace(/\\s+/g,' ').trim();const eventZone=!!e.closest('#dvBetZone,[class*=betzone],[class*=market]');const box=e.closest('nav,form,li,tr,[class*=sport],[class*=league],[class*=filter],[class*=header],section,article,div')||e.parentElement;let label='';if(e.id){const l=document.querySelector(`label[for="${CSS.escape(e.id)}"]`);if(l)label=c(l.innerText||l.textContent)}return {index,id:e.id||'',name:e.name||'',label,aria_label:e.getAttribute('aria-label')||'',title:e.getAttribute('title')||'',context:box?c(box.innerText||box.textContent).slice(0,1200):'',event_zone:eventZone,value:e.value||'',options:Array.from(e.options||[]).map(o=>({text:c(o.textContent),value:o.value,disabled:o.disabled,selected:o.selected}))}})""")
    except Exception:return [],[]
    safe=[];unresolved=[]
    for r in rows:
        joined=' '.join(clean(r.get(k)) for k in ('id','name','label','aria_label','title','context'))
        if r.get('event_zone') is True:continue
        if DANGEROUS_RE.search(joined) or ACCOUNT_RE.search(joined):continue
        if BOARD_SAFE_RE.search(joined):safe.append(r)
        elif any(not bool(o.get('disabled')) for o in r.get('options') or []) and joined:unresolved.append(r)
    return safe,unresolved

def control_identity(r):return [clean(r.get('id')),clean(r.get('role')),strip_price(r.get('text')),clean(r.get('title')),clean(r.get('class_name')),clean(r.get('onclick'))]
def select_identity(r):return [clean(r.get('id')),clean(r.get('name')),clean(r.get('label')).casefold(),strip_price(r.get('context')).casefold()[:500]]
def resolve_control(page,ident):
    ms=[]
    for r in board_controls(page):
        if r.get('classification')!='SAFE_BOARD_NAV':continue
        if (ident[0] and clean(r.get('id'))==ident[0]) or control_identity(r)==ident:ms.append(r)
    return ms[0] if len(ms)==1 else None
def resolve_select(page,ident):
    safe,_=board_selects(page);ms=[r for r in safe if select_identity(r)==ident];return ms[0] if len(ms)==1 else None

def snapshot(page:Page)->dict[str,Any]:
    ctrls=board_controls(page);sels,unresolved_sels=board_selects(page);actions=[];unresolved=[];related=[]
    for r in ctrls:
        if r.get('classification')=='SAFE_BOARD_NAV':actions.append({'kind':'control','identity':control_identity(r)})
        m=RELATED_RE.search(clean(r.get('onclick')))
        if m:related.append({'header_id':int(m.group(1)),'event_id':int(m.group(2))})
    for r in sels:
        sid=select_identity(r)
        for o in r.get('options') or []:
            if not bool(o.get('disabled')):actions.append({'kind':'select_option','identity':sid,'value':clean(o.get('value')),'text':clean(o.get('text'))})
    for r in unresolved_sels:unresolved.append({'kind':'board_select','id':clean(r.get('id')),'label':clean(r.get('label')),'context':strip_price(r.get('context'))[:500]})
    structure={'url':redact_url(page.url),'controls':[control_identity(r) for r in ctrls if r.get('classification')=='SAFE_BOARD_NAV'],'selects':[{'identity':select_identity(r),'value':clean(r.get('value')),'options':[(clean(o.get('value')),clean(o.get('text')),bool(o.get('selected'))) for o in r.get('options') or [] if not bool(o.get('disabled'))]} for r in sels],'visible_related':sorted(related,key=lambda x:(x['header_id'],x['event_id']))}
    return {'state_hash':digest(structure),'actions':actions,'unresolved_market_controls':unresolved,'surface_counts':{'safe_board_controls':len(structure['controls']),'board_selects':len(sels),'visible_related_events':len(related)}}
def apply(page,action)->bool:
    if action.get('kind')=='control':
        r=resolve_control(page,list(action.get('identity') or []))
        if r is None:return False
        try:page.locator("a,button,[role='tab'],[role='button'],[onclick],summary").nth(int(r['index'])).click(timeout=5000,force=True);page.wait_for_timeout(650);return True
        except Exception:return False
    if action.get('kind')=='select_option':
        r=resolve_select(page,list(action.get('identity') or []))
        if r is None:return False
        try:
            loc=page.locator('select').nth(int(r['index']));v=clean(action.get('value'));t=clean(action.get('text'));loc.select_option(value=v,timeout=5000) if v else loc.select_option(label=t,timeout=5000);page.wait_for_timeout(650);return True
        except Exception:return False
    return False

def stable_snapshot(page,reads=3):
    last='';n=0;cur=None
    for _ in range(max(reads*4,reads)):
        cur=snapshot(page);h=cur['state_hash']
        if h==last:n+=1
        else:last=h;n=1
        if n>=reads:return cur,None
        page.wait_for_timeout(250)
    return cur,'STATE_NOT_STABLE'

def direct_crawl(page,max_actions=5000):
    seen=set();errors=[];stable=[];interactions=0
    while interactions<max_actions:
        s,err=stable_snapshot(page,2)
        if err:errors.append({'code':err});break
        if s.get('unresolved_market_controls'):errors.append({'code':'UNRESOLVED_BOARD_CONTROLS','controls':s['unresolved_market_controls'][:50]});break
        nxt=None
        for a in s.get('actions') or []:
            k=json.dumps(a,sort_keys=True,ensure_ascii=False)
            if k not in seen:nxt=(a,k);break
        if nxt:
            a,k=nxt;seen.add(k)
            if not apply(page,a):errors.append({'code':'DIRECT_ACTION_FAILED','action':a});break
            interactions+=1;stable=[];continue
        stable.append(s['state_hash']);stable=stable[-3:]
        if len(stable)==3 and len(set(stable))==1:break
        page.wait_for_timeout(400)
    complete=bool(not errors and interactions<max_actions and len(stable)==3 and len(set(stable))==1)
    return {'complete':complete,'interactions':interactions,'actions_seen':len(seen),'stable_hashes':stable,'blockers':errors or ([{'code':'MAX_ACTIONS_REACHED','limit':max_actions}] if interactions>=max_actions else [])}
def explore_graph(page,reset,max_states=2000,max_edges=20000,max_path=60):
    q=deque([[]]);expanded=set();edges=set();records=[];blockers=[]
    while q:
        if len(expanded)>=max_states:blockers.append({'code':'MAX_STATES_REACHED','limit':max_states});break
        path=q.popleft()
        if len(path)>max_path:blockers.append({'code':'MAX_PATH_LENGTH_REACHED','limit':max_path});break
        if not reset():blockers.append({'code':'RESET_FAILED'});break
        ok=True
        for a in path:
            if not apply(page,a):blockers.append({'code':'REPLAY_ACTION_FAILED','action':a,'path_length':len(path)});ok=False;break
        if not ok:break
        s,err=stable_snapshot(page,3)
        if err:blockers.append({'code':err,'path_length':len(path)});break
        if s.get('unresolved_market_controls'):blockers.append({'code':'UNRESOLVED_MARKET_CONTROLS','controls':s['unresolved_market_controls'][:100]});break
        h=s['state_hash']
        if h in expanded:continue
        expanded.add(h);acts=list(s.get('actions') or []);records.append({'state_hash':h,'path_length':len(path),'action_count':len(acts),'surface_counts':s.get('surface_counts')})
        for a in acts:
            ak=json.dumps(a,ensure_ascii=False,sort_keys=True,separators=(',',':'));edge=(h,ak)
            if edge in edges:continue
            if len(edges)>=max_edges:blockers.append({'code':'MAX_EDGES_REACHED','limit':max_edges});q.clear();break
            edges.add(edge);q.append(path+[a])
    return {'complete':not blockers and not q,'states_explored':len(expanded),'edges_explored':len(edges),'state_records':records,'blockers':blockers}

def main():
    OUT.mkdir(parents=True,exist_ok=True);phase={'name':'idle'};catalogs={'direct':{},'graph':{}};methods={'direct':{},'graph':{}};nav=[]
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True);ctx=b.new_context(viewport={'width':1500,'height':1500},locale='es-DO',timezone_id='America/Santo_Domingo');p=ctx.new_page()
        def on_response(resp):
            name=phase['name']
            if name not in catalogs or not same_site(resp.url) or resp.request.resource_type not in {'xhr','fetch'}:return
            m=xhr_method(resp.url)
            if m:methods[name][m]=methods[name].get(m,0)+1
            try:evs=extract_events(resp.text())
            except Exception:return
            for e in evs:catalogs[name][(e['header_id'],e['event_id'])]=e
        p.on('response',on_response)
        def load_root():
            for i in range(5):
                try:p.goto(START,wait_until='domcontentloaded',timeout=60000);p.wait_for_timeout(3500);return True
                except Exception as ex:nav.append(f'{phase["name"]}:{i+1}:{type(ex).__name__}:{ex}')
                p.wait_for_timeout(1000)
            return False
        phase['name']='direct'
        if not load_root():raise RuntimeError('DIRECT_ROOT_UNAVAILABLE')
        direct=direct_crawl(p)
        phase['name']='graph'
        graph=explore_graph(p,load_root)
        ctx.close();b.close()
    dkeys=set(catalogs['direct']);gkeys=set(catalogs['graph']);only_d=sorted(dkeys-gkeys);only_g=sorted(gkeys-dkeys)
    dtransport=methods['direct'].get('RefreshHeaders',0)>0 and methods['direct'].get('GetUpcomingEvents',0)>0
    gtransport=methods['graph'].get('RefreshHeaders',0)>0 and methods['graph'].get('GetUpcomingEvents',0)>0
    same=bool(dkeys) and dkeys==gkeys
    complete=bool(direct['complete'] and graph['complete'] and dtransport and gtransport and same)
    union={**catalogs['direct'],**catalogs['graph']}
    res={'captured_at_local':datetime.now(TZ).isoformat(),'status':'DUAL_PUBLIC_CATALOG_COMPLETE' if complete else 'DUAL_PUBLIC_CATALOG_INCOMPLETE','production_valid':complete,'direct_complete':direct['complete'],'board_graph_complete':graph['complete'],'direct_transport_seen':dtransport,'graph_transport_seen':gtransport,'independent_catalog_sets_equal':same,'direct_event_count':len(dkeys),'graph_event_count':len(gkeys),'union_event_count':len(union),'only_direct':[{'header_id':h,'event_id':e} for h,e in only_d],'only_graph':[{'header_id':h,'event_id':e} for h,e in only_g],'direct':direct,'graph':graph,'xhr_method_counts':methods,'events':[union[k] for k in sorted(union)],'nav_errors':nav,'negative_catalog_inference_allowed':complete,'guard':'Public read-only dual discovery. No wager/stake/coupon/account control is traversed. Any unresolved board select/graph bound/catalog mismatch fails closed.'}
    (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8');summary={k:res[k] for k in ['captured_at_local','status','production_valid','direct_complete','board_graph_complete','direct_transport_seen','graph_transport_seen','independent_catalog_sets_equal','direct_event_count','graph_event_count','union_event_count','only_direct','only_graph']};summary['direct_metrics']={k:direct[k] for k in ['interactions','actions_seen','blockers']};summary['graph_metrics']={k:graph[k] for k in ['states_explored','edges_explored','blockers']};(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
    raise SystemExit(0 if complete else 3)
if __name__=='__main__':main()
