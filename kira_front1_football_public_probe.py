from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright

OUT = Path('front1_football_contract_inventory')
OUT.mkdir(parents=True, exist_ok=True)
START_URL = 'https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
FOOTBALL_LEAGUES = ['USA','SPAIN','AUSTRIA','GERMANY','ITALY','FRANCE','PORTUGAL','NETHERLANDS','SCOTLAND','BELGIUM']
TERMS = {
    'double_chance': re.compile(r'(?i)double\s+chance|doble\s+oportunidad'),
    'draw_no_bet': re.compile(r'(?i)draw\s+no\s+bet|empate\s+(?:no\s+)?apuesta|sin\s+empate'),
    'team_total': re.compile(r'(?i)team\s+total|total\s+(?:del|por|solo\s+por)\s+equipo'),
    'winning_margin': re.compile(r'(?i)winning\s+margin|margen\s+de\s+victoria'),
    'handicap': re.compile(r'(?i)handicap|hándicap'),
    'moneyline': re.compile(r'(?i)money\s*line|línea\s+de\s+dinero|linea\s+de\s+dinero'),
}


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(x):
    return re.sub(r'\s+', ' ', str(x or '').replace('\xa0',' ')).strip()


def redact_url(url: str) -> str:
    try:
        p = urlsplit(url)
        q=[]
        for k,v in parse_qsl(p.query, keep_blank_values=True):
            if k.casefold() in {'stoken','_session','session','token'}:
                v='REDACTED'
            q.append((k,v))
        return urlunsplit((p.scheme,p.netloc,p.path,urlencode(q),p.fragment))
    except Exception:
        return url


def redact_text(text: str) -> str:
    text=str(text or '')
    text=re.sub(r'(?i)(stoken|_session|session|token)=([^&\'"\\\s]+)', r'\1=REDACTED', text)
    text=re.sub(r'(?i)(SessionID\s*[=:]\s*[\'"])[^\'"]+', r'\1REDACTED', text)
    text=re.sub(r'(?i)(PlayerInfo\s*[=:]\s*[\'"])[A-Za-z0-9+/=_-]{20,}', r'\1REDACTED', text)
    return text


def same_site(url: str) -> bool:
    try:
        return (urlsplit(url).hostname or '').endswith('juancitosport.com.do')
    except Exception:
        return False


def extract_event_refs(body: str):
    out=[]
    for m in re.finditer(r'newE\s*=\s*new Event\((.*?)\);\s*newHeader\.AddEvent', body or '', re.S):
        payload=m.group(1)
        head=re.match(r'\s*(-?\d+)\s*,\s*(\d+)\s*,',payload)
        if not head: continue
        header_id,event_id=int(head.group(1)),int(head.group(2))
        sport=None
        for candidate in ('Basketball','Tennis','Soccer','Baseball'):
            if f"'{candidate}'" in payload:
                sport=candidate; break
        title_m=re.match(r"\s*-?\d+\s*,\s*\d+\s*,\s*'((?:\\'|[^'])*)'",payload)
        title=title_m.group(1).replace("\\'", "'") if title_m else ''
        out.append({'header_id':header_id,'event_id':event_id,'sport':sport,'title':title})
    dedup={(x['header_id'],x['event_id']):x for x in out}
    return list(dedup.values())


def click_exact_visible(page,label):
    loc=page.get_by_text(label, exact=True)
    for i in range(loc.count()):
        try:
            n=loc.nth(i)
            if n.is_visible():
                n.scroll_into_view_if_needed(timeout=5000)
                n.click(timeout=8000, force=True)
                return True
        except Exception:
            pass
    return False


def call_related(page,h,e):
    try:
        if not page.evaluate("typeof RelatedEvents === 'function'"):
            return False,'RelatedEvents_not_available'
        page.evaluate('([h,e]) => { RelatedEvents(h,e,1,0); }',[h,e])
        page.wait_for_timeout(3500)
        return True,None
    except Exception as exc:
        return False,f'{type(exc).__name__}: {exc}'


def collect_market_rows(page,event):
    if page.locator('#dvBetZone').count()==0:
        return []
    rows=page.locator('#dvBetZone tr').evaluate_all(r"""
    rows => {
      const clean=s=>(s||'').replace(/\s+/g,' ').trim();
      const participantName=r=>{
        const n=r.querySelector('.colParticipantInfoParticipant,.SchUpcomingParticipant,.upcomingParticipantName');
        return n?clean(n.innerText||n.textContent):'';
      };
      const section=el=>{
        let node=el;
        while(node && node.id!=='dvBetZone' && node!==document.body){
          let prev=node.previousElementSibling;
          while(prev){
            if(prev.matches && prev.matches('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]')){
              const t=clean(prev.innerText||prev.textContent); if(t) return t;
            }
            if(prev.querySelectorAll){
              const hs=prev.querySelectorAll('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]');
              if(hs.length){ const t=clean(hs[hs.length-1].innerText||hs[hs.length-1].textContent); if(t) return t; }
            }
            prev=prev.previousElementSibling;
          }
          node=node.parentElement;
        }
        return '';
      };
      return rows.map((r,index)=>{
        const participant_name=participantName(r);
        const actions=Array.from(r.querySelectorAll('a,button,[onclick],.tooltip_addBet')).map(a=>({
          text:clean(a.innerText||a.textContent), id:a.id||'',
          class_name:typeof a.className==='string'?a.className:'',
          title:a.getAttribute('title')||'', aria_label:a.getAttribute('aria-label')||'',
          row_text:clean(r.innerText||r.textContent), participant_name,
          actionable:a.classList?a.classList.contains('tooltip_addBet'):false,
          locked:a.classList?a.classList.contains('cellCandado'):false
        }));
        return {index,section_title:section(r),participant_name,text:clean(r.innerText||r.textContent),actions};
      });
    }
    """)
    out=[]
    for row in rows:
        for a in row.get('actions') or []:
            out.append({
                'captured_at_utc':now(),
                'header_id':event.get('header_id'),
                'event_id':event.get('event_id'),
                'event_title':event.get('title'),
                'sport':'football',
                'section_title':clean(row.get('section_title')),
                'participant_name':clean(a.get('participant_name')),
                'action_text':clean(a.get('text')),
                'action_id':clean(a.get('id')),
                'action_class':clean(a.get('class_name')),
                'actionable':bool(a.get('actionable')),
                'locked':bool(a.get('locked')),
                'row_text':clean(a.get('row_text')),
                'title':clean(a.get('title')),
                'aria_label':clean(a.get('aria_label')),
            })
    return out


def main():
    network=[]; events={}; snapshots=[]; actions=[]; league_clicks=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':1400},locale='es-DO',timezone_id='America/Santo_Domingo',user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36')
        page=ctx.new_page()
        def on_response(resp):
            req=resp.request
            if not same_site(resp.url) or req.resource_type not in {'xhr','fetch'}: return
            rec={'url':redact_url(resp.url),'status':resp.status,'method':req.method,'captured_at_utc':now()}
            try:
                body=resp.text()
                preview=redact_text(body[:300000])
                rec['body_preview']=preview
                for ev in extract_event_refs(body): events[(ev['header_id'],ev['event_id'])]=ev
            except Exception as exc:
                rec['body_error']=f'{type(exc).__name__}: {exc}'
            network.append(rec)
        page.on('response',on_response)
        nav={'start_url':START_URL,'captured_at_utc':now()}
        try:
            r=page.goto(START_URL,wait_until='domcontentloaded',timeout=120000)
            nav['status']=r.status if r else None
        except Exception as exc:
            nav['error']=f'{type(exc).__name__}: {exc}'
        page.wait_for_timeout(15000)
        nav['final_url']=redact_url(page.url)
        for label in FOOTBALL_LEAGUES:
            clicked=click_exact_visible(page,label)
            league_clicks.append({'label':label,'clicked':clicked})
            if clicked: page.wait_for_timeout(1800)
        # Let any GetUpcomingEvents XHR settle and then select up to 12 Soccer events.
        page.wait_for_timeout(3000)
        soccer=[e for e in events.values() if e.get('sport')=='Soccer'][:12]
        details=[]
        for ev in soccer:
            ok,err=call_related(page,ev['header_id'],ev['event_id'])
            details.append({**ev,'related_called':ok,'error':err})
            if not ok: continue
            body=''
            try: body=redact_text(page.locator('body').inner_text(timeout=30000))
            except Exception: pass
            snapshots.append({'captured_at_utc':now(),'event':ev,'body':body[:150000],'url':redact_url(page.url)})
            actions.extend(collect_market_rows(page,ev))
        ctx.close(); browser.close()

    # Build term evidence only from public sanitized DOM/XHR. No market absence claim from incomplete capture.
    term_hits={k:[] for k in TERMS}
    corpora=[]
    for s in snapshots: corpora.append(('snapshot:'+str(s['event']['event_id']),s.get('body','')))
    for i,n in enumerate(network): corpora.append((f'network:{i}',n.get('body_preview','')))
    for row in actions: corpora.append((f"action:{row.get('event_id')}:{row.get('action_id')}",json.dumps(row,ensure_ascii=False)))
    for source,text in corpora:
        for name,rx in TERMS.items():
            for m in rx.finditer(text or ''):
                lo=max(0,m.start()-180); hi=min(len(text),m.end()+260)
                term_hits[name].append({'source':source,'snippet':clean(text[lo:hi])})
                if len(term_hits[name])>=50: break
    dc_actions=[]
    for row in actions:
        corpus=' '.join(str(row.get(k) or '') for k in ('section_title','action_text','row_text','title','aria_label'))
        if TERMS['double_chance'].search(corpus): dc_actions.append(row)
    family_leads={name:len(hits) for name,hits in term_hits.items()}
    summary={
        'captured_at_utc':now(), 'execution':'anonymous_public_read_only',
        'source_logic':'PR65 8a1f373d public BOSS/RelatedEvents mechanics; standalone transport only',
        'navigation':nav,'league_clicks':league_clicks,
        'event_refs_seen':len(events),'soccer_events_examined':len([d for d in details if d.get('related_called')]),
        'soccer_event_details':details,'market_action_rows':len(actions),
        'actionable_rows':sum(1 for r in actions if r.get('actionable')),
        'double_chance_action_rows':len(dc_actions),'term_hit_counts':family_leads,
        'coverage_complete':False,
        'guard':'Discovery evidence only. coverage_complete=false means no missing term may be interpreted as Juancito market absence. No science, settlement, accumulator or wager conclusion is inherited.'
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    (OUT/'term_hits.json').write_text(json.dumps(term_hits,indent=2,ensure_ascii=False),encoding='utf-8')
    (OUT/'football_market_actions.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in actions)+('\n' if actions else ''),encoding='utf-8')
    (OUT/'double_chance_actions.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in dc_actions)+('\n' if dc_actions else ''),encoding='utf-8')
    # Persist compact network metadata and only term-hit snippets, not full XHR bodies.
    (OUT/'network_meta.json').write_text(json.dumps([{k:v for k,v in n.items() if k!='body_preview'} for n in network],indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
