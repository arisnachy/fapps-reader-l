from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright

OUT = Path('front1_football_contract_inventory_v3_expanded')
OUT.mkdir(parents=True, exist_ok=True)
START = 'https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
LEAGUES = ['USA','SPAIN','AUSTRIA','GERMANY','ITALY','FRANCE','PORTUGAL','NETHERLANDS','SCOTLAND','BELGIUM']
TERMS = {
    'double_chance': re.compile(r'(?i)double\s+chance|doble\s+oportunidad|(?:^|\s)(?:1x|x2|12)(?:\s|$)'),
    'draw_no_bet': re.compile(r'(?i)draw\s+no\s+bet|empate\s+(?:no\s+)?apuesta|sin\s+empate|\bdnb\b'),
    'team_total': re.compile(r'(?i)team\s+total|total\s+(?:del|de|por|solo\s+por)\s+equipo|total\s+equipo'),
    'winning_margin': re.compile(r'(?i)winning\s+margin|margen\s+de\s+victoria'),
    'handicap': re.compile(r'(?i)handicap|hándicap'),
    'both_teams_score': re.compile(r'(?i)both\s+teams\s+to\s+score|ambos\s+equipos\s+(?:marcan|anotan)'),
}

def now(): return datetime.now(timezone.utc).isoformat()
def clean(v): return re.sub(r'\s+', ' ', str(v or '').replace('\xa0',' ')).strip()

def redact_url(url):
    try:
        p=urlsplit(url); q=[]
        for k,v in parse_qsl(p.query, keep_blank_values=True):
            if k.casefold() in {'stoken','_session','session','token'}: v='REDACTED'
            q.append((k,v))
        return urlunsplit((p.scheme,p.netloc,p.path,urlencode(q),p.fragment))
    except Exception: return url

def same_site(url):
    try: return (urlsplit(url).hostname or '').endswith('juancitosport.com.do')
    except Exception: return False

def click_exact(page,label):
    loc=page.get_by_text(label,exact=True)
    for i in range(loc.count()):
        try:
            n=loc.nth(i)
            if n.is_visible():
                n.scroll_into_view_if_needed(timeout=3000); n.click(timeout=6000,force=True); return True
        except Exception: pass
    return False

def related_links(page):
    try:
        vals=page.locator("a[onclick*='RelatedEvents']").evaluate_all("els=>els.map(e=>({text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),onclick:e.getAttribute('onclick')||''}))")
    except Exception: return []
    out=[]
    for x in vals:
        m=re.search(r'RelatedEvents\((\d+)\s*,\s*(\d+)',x.get('onclick',''))
        if m: out.append({'header_id':int(m.group(1)),'event_id':int(m.group(2)),'anchor_text':clean(x.get('text')),'source':'dom_related'})
    return out

def call_related(page,h,e):
    try:
        if not page.evaluate("typeof RelatedEvents === 'function'"): return False,'RelatedEvents_not_available'
        page.evaluate('([h,e])=>RelatedEvents(h,e,1,0)',[h,e]); page.wait_for_timeout(2600); return True,None
    except Exception as exc: return False,f'{type(exc).__name__}: {exc}'

def expand_more(page,limit=24):
    selector="#dvBetZone a,#dvBetZone button,#dvBetZone [onclick]"
    opened=0
    # Re-query on each pass because BOSS can rerender after an expansion.
    for _ in range(limit):
        target=None
        loc=page.locator(selector)
        for i in range(min(loc.count(),1400)):
            try:
                node=loc.nth(i)
                txt=clean(node.inner_text(timeout=250)).casefold()
                title=clean(node.get_attribute('title')).casefold()
                if txt not in {'más','mas','more'} and title not in {'más','mas','more'}: continue
                if not node.is_visible(): continue
                # Avoid repeatedly clicking an already-expanded control when aria-expanded is explicit.
                if clean(node.get_attribute('aria-expanded')).casefold()=='true': continue
                target=node; break
            except Exception: continue
        if target is None: break
        try:
            target.click(timeout=3000,force=True); page.wait_for_timeout(650); opened+=1
        except Exception: break
    return opened

def section_titles(page):
    try:
        vals=page.locator("#dvBetZone .SchBZHeaderTitle,#dvBetZone .SchBZSubHeaderTitle,#dvBetZone [class*='HeaderTitle']").all_inner_texts()
        return [clean(x) for x in vals if clean(x)]
    except Exception: return []

def structured_selects(page,event):
    try:
        return page.locator('#dvBetZone select').evaluate_all(r"""els=>{const c=s=>(s||'').replace(/\s+/g,' ').trim(); const sec=el=>{let n=el;while(n&&n.id!=='dvBetZone'&&n!==document.body){let p=n.previousElementSibling;while(p){if(p.matches&&p.matches('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]')){let t=c(p.innerText||p.textContent);if(t)return t;}if(p.querySelectorAll){let hs=p.querySelectorAll('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]');if(hs.length){let t=c(hs[hs.length-1].innerText||hs[hs.length-1].textContent);if(t)return t;}}p=p.previousElementSibling;}n=n.parentElement;}return '';};return els.map((e,i)=>{let row=e.closest('tr');let pn=row?row.querySelector('.colParticipantInfoParticipant,.SchUpcomingParticipant,.upcomingParticipantName'):null;let label='';if(e.id){let lab=document.querySelector(`label[for="${CSS.escape(e.id)}"]`);if(lab)label=c(lab.innerText||lab.textContent);}return {index:i,id:e.id||'',name:e.name||'',value:e.value||'',label,aria_label:e.getAttribute('aria-label')||'',title:e.getAttribute('title')||'',section_title:sec(e),participant_name:pn?c(pn.innerText||pn.textContent):'',row_text:row?c(row.innerText||row.textContent):'',options:Array.from(e.options||[]).map(o=>({text:c(o.textContent),value:o.value,selected:o.selected,disabled:o.disabled}))};});}""")
    except Exception: return []

def market_actions(page,event):
    if page.locator('#dvBetZone').count()==0:return []
    data=page.locator('#dvBetZone tr').evaluate_all(r"""rows=>{const c=s=>(s||'').replace(/\s+/g,' ').trim(); const sec=el=>{let n=el;while(n&&n.id!=='dvBetZone'&&n!==document.body){let p=n.previousElementSibling;while(p){if(p.matches&&p.matches('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]')){let t=c(p.innerText||p.textContent);if(t)return t;}if(p.querySelectorAll){let hs=p.querySelectorAll('.SchBZHeaderTitle,.SchBZSubHeaderTitle,[class*="HeaderTitle"]');if(hs.length){let t=c(hs[hs.length-1].innerText||hs[hs.length-1].textContent);if(t)return t;}}p=p.previousElementSibling;}n=n.parentElement;}return '';};return rows.map(r=>{let pn=r.querySelector('.colParticipantInfoParticipant,.SchUpcomingParticipant,.upcomingParticipantName');let participant=pn?c(pn.innerText||pn.textContent):'';return {section:sec(r),row_text:c(r.innerText||r.textContent),actions:Array.from(r.querySelectorAll('a,button,[onclick],.tooltip_addBet')).map(a=>({text:c(a.innerText||a.textContent),id:a.id||'',class_name:typeof a.className==='string'?a.className:'',title:a.getAttribute('title')||'',aria:a.getAttribute('aria-label')||'',participant,onclick:a.getAttribute('onclick')||'',actionable:a.classList?a.classList.contains('tooltip_addBet'):false,locked:a.classList?a.classList.contains('cellCandado'):false}))};});}""")
    out=[]
    for row in data:
        for a in row.get('actions') or []:
            out.append({'captured_at_utc':now(),'header_id':event['header_id'],'event_id':event['event_id'],'source_league':event.get('source_league',''),'section_title':clean(row.get('section')),'participant_name':clean(a.get('participant')),'action_text':clean(a.get('text')),'action_id':clean(a.get('id')),'action_class':clean(a.get('class_name')),'title':clean(a.get('title')),'aria_label':clean(a.get('aria')),'row_text':clean(row.get('row_text')),'onclick':clean(a.get('onclick'))[:1000],'actionable':bool(a.get('actionable')),'locked':bool(a.get('locked'))})
    return out

def main():
    candidates={}; clicks=[]; details=[]; actions=[]; selects=[]; event_sections={}; body_hits={k:[] for k in TERMS}; network=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True); ctx=browser.new_context(viewport={'width':1440,'height':1400},locale='es-DO',timezone_id='America/Santo_Domingo'); page=ctx.new_page()
        def on_resp(resp):
            if not same_site(resp.url) or resp.request.resource_type not in {'xhr','fetch'}: return
            network.append({'url':redact_url(resp.url),'status':resp.status,'method':resp.request.method,'captured_at_utc':now()})
        page.on('response',on_resp)
        nav={'start_url':START,'captured_at_utc':now()}
        try:r=page.goto(START,wait_until='domcontentloaded',timeout=120000);nav['status']=r.status if r else None
        except Exception as exc:nav['error']=f'{type(exc).__name__}: {exc}'
        page.wait_for_timeout(14000);nav['final_url']=redact_url(page.url)
        for label in LEAGUES:
            ok=click_exact(page,label);clicks.append({'label':label,'clicked':ok})
            if ok:
                page.wait_for_timeout(1800)
                for ev in related_links(page):
                    ev['source_league']=label;candidates[(ev['header_id'],ev['event_id'])]=ev
        chosen=list(candidates.values())[:12]
        for ev in chosen:
            ok,err=call_related(page,ev['header_id'],ev['event_id'])
            rec={**ev,'related_called':ok,'error':err,'expanders_opened':0}
            if not ok: details.append(rec); continue
            rec['expanders_opened']=expand_more(page,24)
            page.wait_for_timeout(500)
            secs=section_titles(page);event_sections[str(ev['event_id'])]=secs
            ss=structured_selects(page,ev)
            for s in ss:s.update({'event_id':ev['event_id'],'header_id':ev['header_id'],'source_league':ev.get('source_league',''),'captured_at_utc':now()})
            selects.extend(ss); actions.extend(market_actions(page,ev))
            try:body=clean(page.locator('#dvBetZone').inner_text(timeout=15000))
            except Exception:body=''
            for name,rx in TERMS.items():
                for m in rx.finditer(body):
                    if len(body_hits[name])>=30:break
                    body_hits[name].append({'event_id':ev['event_id'],'source_league':ev.get('source_league',''),'snippet':body[max(0,m.start()-220):min(len(body),m.end()+420)]})
            details.append(rec)
        ctx.close();browser.close()
    # Compact summaries. Presence means observation only; missing term is never treated as absence with incomplete league coverage.
    section_counter=Counter(x for arr in event_sections.values() for x in arr)
    prefix_counter=Counter((re.match(r'^([A-Za-z]+)',a.get('action_id','') or '') or [None,'(blank)'])[1] for a in actions)
    term_action={k:[] for k in TERMS}
    for a in actions:
        corpus=' | '.join(clean(a.get(f)) for f in ('section_title','participant_name','action_text','action_id','row_text','title','aria_label'))
        for name,rx in TERMS.items():
            if rx.search(corpus) and len(term_action[name])<30: term_action[name].append(a)
    select_markers={k:[] for k in TERMS}
    numeric_selects=[]
    for s in selects:
        corpus=' | '.join(clean(s.get(f)) for f in ('id','name','label','aria_label','title','section_title','participant_name','row_text'))+' | '+' | '.join(clean(o.get('text')) for o in s.get('options') or [])
        nums=[]
        for o in s.get('options') or []:
            nums.extend(re.findall(r'(?<!\d)[-+]?\d+(?:\.\d+)?(?!\d)',clean(o.get('text'))))
        if nums:numeric_selects.append(s)
        for name,rx in TERMS.items():
            if rx.search(corpus) and len(select_markers[name])<30:select_markers[name].append(s)
    summary={'captured_at_utc':now(),'execution':'anonymous_public_read_only','transport':'standalone mirror of PR65 structured probe expand_visible_more + select inventory','navigation':nav,'league_clicks':clicks,'soccer_candidates':len(candidates),'soccer_events_examined':sum(1 for d in details if d['related_called']),'event_details':details,'expanders_opened_total':sum(d.get('expanders_opened',0) for d in details),'unique_section_titles':section_counter.most_common(),'action_rows':len(actions),'actionable_rows':sum(1 for a in actions if a['actionable']),'action_id_prefix_counts':prefix_counter.most_common(),'select_count':len(selects),'numeric_select_count':len(numeric_selects),'body_term_hit_counts':{k:len(v) for k,v in body_hits.items()},'action_term_hit_counts':{k:len(v) for k,v in term_action.items()},'select_term_hit_counts':{k:len(v) for k,v in select_markers.items()},'coverage_complete':False,'guard':'Read-only market discovery. No bet cell is clicked; only public More expanders are opened. Presence proves exposure in captured event only. Missing families cannot be declared unavailable while coverage_complete=false. No science or settlement result is inferred.'}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    (OUT/'event_sections.json').write_text(json.dumps(event_sections,indent=2,ensure_ascii=False),encoding='utf-8')
    (OUT/'term_hits.json').write_text(json.dumps({'body':body_hits,'actions':term_action,'selects':select_markers},indent=2,ensure_ascii=False),encoding='utf-8')
    (OUT/'market_actions.jsonl').write_text('\n'.join(json.dumps(a,ensure_ascii=False) for a in actions)+('\n' if actions else ''),encoding='utf-8')
    (OUT/'selects.jsonl').write_text('\n'.join(json.dumps(s,ensure_ascii=False) for s in selects)+('\n' if selects else ''),encoding='utf-8')
    (OUT/'numeric_selects.jsonl').write_text('\n'.join(json.dumps(s,ensure_ascii=False) for s in numeric_selects)+('\n' if numeric_selects else ''),encoding='utf-8')
    (OUT/'network_meta.json').write_text(json.dumps(network,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
