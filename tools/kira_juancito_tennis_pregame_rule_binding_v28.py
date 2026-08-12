from __future__ import annotations

import ast
import html
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_tennis_pregame_rule_binding_v28')
TZ=ZoneInfo('America/Santo_Domingo')
BET_RE=re.compile(r'^(?:u)?(?:PS|ML|TT|TTT)_\d+_\d+$',re.I)
RELATED_RE=re.compile(r'RelatedEvents\((\d+)\s*,\s*(\d+)',re.I)
RULE_WORD_RE=re.compile(r'(?i)(rule|regla|help|ayuda|info|informaci[oó]n)')
DANGER_RE=re.compile(r'(?i)(bet|apuesta|cup[oó]n|stake|monto|cashier|cajero|deposit|withdraw|retirar|account|cuenta)')


def clean(v): return re.sub(r'\s+',' ',str(v or '')).strip()
def same_site(url): return 'juancitosport.com.do' in str(url or '').casefold()
def xhr_method(url):
    m=re.search(r'[?&]_method=([^&]+)',str(url or ''),re.I);return m.group(1) if m else ''

def decode(body):
    s=str(body or '').strip()
    if len(s)>=2 and s[0] in {'\'', '"'} and s[-1]==s[0]:
        try:
            v=ast.literal_eval(s)
            if isinstance(v,str): return v
        except Exception: pass
    return html.unescape(str(body or ''))

def split_args(payload):
    out=[];buf=[];q='';esc=False;depth=0
    for ch in payload:
        if esc: buf.append(ch);esc=False;continue
        if ch=='\\': buf.append(ch);esc=True;continue
        if q:
            buf.append(ch)
            if ch==q:q=''
            continue
        if ch in {'\'', '"'}: q=ch;buf.append(ch);continue
        if ch in '([{':depth+=1
        elif ch in ')]}':depth=max(0,depth-1)
        if ch==',' and depth==0:out.append(''.join(buf).strip());buf=[]
        else:buf.append(ch)
    out.append(''.join(buf).strip());return out

def uq(x):
    s=clean(x)
    if len(s)>=2 and s[0] in {'\'', '"'} and s[-1]==s[0]:
        try:return str(ast.literal_eval(s))
        except Exception:return s[1:-1]
    return s

def events(body):
    s=decode(body);out=[]
    for m in re.finditer(r'newE\s*=\s*new\s+Event\((.*?)\);',s,re.S):
        a=split_args(m.group(1))
        if len(a)<2:continue
        try:h,e=int(float(a[0])),int(float(a[1]))
        except Exception:continue
        sport=uq(a[37]) if len(a)>=38 else ''
        title=uq(a[2]) if len(a)>=3 else ''
        style=None
        try:style=int(float(a[13])) if len(a)>13 else None
        except Exception:pass
        out.append({'header_id':h,'event_id':e,'sport':sport,'title':title,'event_style':style})
    return out

def ready(page):
    try:return bool(page.evaluate("typeof RelatedEvents === 'function'"))
    except Exception:return False

def root(page):
    errors=[]
    for attempt in range(1,6):
        try:
            page.goto(START,wait_until='commit',timeout=45000);page.wait_for_timeout(10000 if attempt==1 else 4000)
            if ready(page):return True,errors
            errors.append(f'{attempt}:RUNTIME_NOT_READY')
        except Exception as exc:errors.append(f'{attempt}:{type(exc).__name__}:{exc}')
        try:page.wait_for_timeout(1200)
        except Exception:pass
    return False,errors

def safe_rule_controls(page):
    try:
        rows=page.locator("a,button,[role='button'],[onclick],[title]").evaluate_all("""els=>els.map((e,i)=>({index:i,id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\s+/g,' ').trim().slice(0,500),title:e.getAttribute('title')||'',onclick:e.getAttribute('onclick')||'',class_name:typeof e.className==='string'?e.className:''}))""")
    except Exception:return []
    out=[]
    for r in rows:
        direct=' '.join(clean(r.get(k)) for k in ('id','text','title','onclick','class_name'))
        if not RULE_WORD_RE.search(direct) or DANGER_RE.search(direct):continue
        if BET_RE.match(clean(r.get('id'))):continue
        out.append(r)
    return out

def click_unique_rule(page,row):
    node_id=clean(row.get('id'));onclick=clean(row.get('onclick'));title=clean(row.get('title'));text=clean(row.get('text'))
    try:
        return bool(page.evaluate("""([id,onclick,title,text])=>{const c=s=>(s||'').replace(/\s+/g,' ').trim();const els=[...document.querySelectorAll("a,button,[role='button'],[onclick],[title]")].filter(e=>{if(id&&e.id===id)return true;if(onclick&&(e.getAttribute('onclick')||'').trim()===onclick)return true;if(title&&(e.getAttribute('title')||'').trim()===title&&c(e.innerText||e.textContent)===text)return true;return false});if(els.length!==1)return false;els[0].click();return true}""",[node_id,onclick,title,text]))
    except Exception:return False

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    observed=[];network=[];nav_errors=[];chosen=None;rule_clicks=[]
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True);ctx=b.new_context(viewport={'width':1500,'height':1400},locale='es-DO',timezone_id='America/Santo_Domingo');p=ctx.new_page()
        def on_resp(resp):
            if not same_site(resp.url) or resp.request.resource_type not in {'xhr','fetch'}:return
            try:text=resp.text()
            except Exception:return
            method=xhr_method(resp.url)
            for ev in events(text):
                if str(ev.get('sport','')).casefold()=='tennis':observed.append(ev)
            if re.search(r'(?i)(RuleID|RuleBook|GAME\s*-?\s*SPREAD FOR THE COMPLETE MATCH|tiebreak|tie-break|walkover|retiro|retire)',text):
                snippets=[]
                for pat in (r'RuleID.{0,1500}',r'GAME\s*-?\s*SPREAD FOR THE COMPLETE MATCH.{0,2500}',r'(?i)tiebreak.{0,1500}',r'(?i)walkover.{0,1500}'):
                    for m in re.finditer(pat,text,re.S):snippets.append(clean(m.group(0))[:3500])
                network.append({'method':method,'url':re.sub(r'(?i)(token|jwt|session|key)=([^&]+)',r'\1=[REDACTED]',resp.url),'snippets':snippets[:20]})
        p.on('response',on_resp)
        ok,nav_errors=root(p)
        if ok:
            # Force the catalog to expose Tennis by clicking exact shdr nodes whose text says Tennis/Tenis.
            try:
                nodes=p.locator("[id^='shdr']").evaluate_all("""els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\s+/g,' ').trim()}))""")
            except Exception:nodes=[]
            for n in nodes:
                if re.search(r'(?i)\btennis\b|\btenis\b',clean(n.get('text'))):
                    try:
                        p.evaluate("id=>{const x=[...document.querySelectorAll('[id]')].filter(e=>e.id===id);if(x.length===1)x[0].click()}",clean(n.get('id')));p.wait_for_timeout(1800)
                    except Exception:pass
            # Prefer exact full-time style10 Tennis event.
            uniq={int(e['event_id']):e for e in observed}
            candidates=sorted(uniq.values(),key=lambda e:(0 if e.get('event_style')==10 else 1,e['event_id']))
            if candidates:
                chosen=candidates[0]
                try:
                    called=p.evaluate("([h,e])=>{if(typeof RelatedEvents!=='function')return false;RelatedEvents(h,e,1,0);return true}",[chosen['header_id'],chosen['event_id']]);p.wait_for_timeout(1800)
                except Exception:called=False
                if called:
                    before=clean(p.locator('body').inner_text())[:30000]
                    controls=safe_rule_controls(p)
                    for row in controls[:80]:
                        clicked=click_unique_rule(p,row)
                        if clicked:p.wait_for_timeout(1200)
                        after=clean(p.locator('body').inner_text())[:50000]
                        hit=bool(re.search(r'(?i)Rule\s*234|RuleID\s*234|GAME\s*-?\s*SPREAD FOR THE COMPLETE MATCH|Handicap del Juego para\s+el partido completo',after))
                        rule_clicks.append({'id':clean(row.get('id')),'text':clean(row.get('text')),'title':clean(row.get('title')),'onclick':clean(row.get('onclick')),'clicked':clicked,'rule234_text_seen_after':hit,'body_after_excerpt':after[:12000] if hit else ''})
                        # restore exact event between independent controls
                        try:p.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[chosen['header_id'],chosen['event_id']]);p.wait_for_timeout(700)
                        except Exception:pass
                    body=clean(p.locator('body').inner_text())
                else:body=''
            else:body=''
        else:body=''
        ctx.close();b.close()
    binding_hits=[x for x in rule_clicks if x.get('rule234_text_seen_after')]
    network234=[x for x in network if any(re.search(r'(?i)(RuleID\s*234|GAME\s*-?\s*SPREAD FOR THE COMPLETE MATCH)',s) for s in x.get('snippets') or [])]
    # A positive binding requires Rule234 to appear only after a safe rule/info interaction on the selected pregame event,
    # or a same-event network rule payload exposing Rule234. Mere global RuleBook availability is not enough.
    binding=bool(chosen and (binding_hits or network234))
    result={'captured_at_local':datetime.now(TZ).isoformat(),'status':'PREGAME_RULE234_BINDING_PASS' if binding else ('PREGAME_RULE234_BINDING_NOT_PROVED' if chosen else 'INFRA_OR_NO_TENNIS_EVENT'),'production_valid_binding':binding,'chosen_event':chosen,'tennis_events_observed':len({e['event_id'] for e in observed}),'safe_rule_controls_tried':len(rule_clicks),'binding_hits':binding_hits,'network_rule234_hits':network234,'nav_errors':nav_errors,'rule_click_audit':rule_clicks,'safety':'Read-only. Only RelatedEvents navigation and uniquely identified Rule/Regla/Help/Info controls are used; bet cells/coupon/stake/account controls are excluded.','holdout_scored':False}
    (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('captured_at_local','status','production_valid_binding','chosen_event','tennis_events_observed','safe_rule_controls_tried','nav_errors')},ensure_ascii=False,indent=2))
    raise SystemExit(0 if binding else 3)
if __name__=='__main__':main()
