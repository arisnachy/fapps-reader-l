from __future__ import annotations
import json,re,urllib.parse
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_tierb_advanced_direct_v16')
TZ=ZoneInfo('America/Santo_Domingo')
TARGETS=[(2037,1961877,'Shandong Luneng Taishan',1),(2015,1962330,'Ruch Chorzow',2),(2059,1959023,'LASK Linz',3)]

def c(x): return re.sub(r'\s+',' ',str(x or '').replace('\xa0',' ')).strip()
def safe_url(u):
    try:
        z=urllib.parse.urlsplit(u); return urllib.parse.urlunsplit((z.scheme,z.netloc,z.path,'',''))
    except Exception: return ''
def redact(s):
    s=re.sub(r'(?i)(token|authorization|jwt|session|cookie)["\'\s:=]+[A-Za-z0-9._~+/=-]{8,}',r'\1=[REDACTED]',s)
    s=re.sub(r'https?://[^\s"\']+\?[^\s"\']+',lambda m:safe_url(m.group(0)),s)
    s=re.sub(r'\b[A-Za-z0-9_-]{36,}\b','[REDACTED_LONG_TOKEN]',s)
    return c(s)
def relevant(text,team):
    low=text.lower(); keys=[team.lower(),'handicap','team total','team goals','double chance','draw no bet','total','+1.5','1.5','spread','alternative']
    return any(k in low for k in keys)
def main():
    OUT.mkdir(parents=True,exist_ok=True); nav=[]; results=[]
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True)
        ctx=b.new_context(locale='es-DO',timezone_id='America/Santo_Domingo',viewport={'width':1800,'height':2200})
        host=ctx.new_page(); loaded=False
        for a in range(4):
            try:
                host.goto(START,wait_until='commit',timeout=45000); host.wait_for_timeout(10000)
                if host.locator('#tblSH_53').count(): loaded=True; break
            except Exception as ex: nav.append(f'{a+1}:{type(ex).__name__}:{ex}')
        if not loaded: b.close(); raise RuntimeError('BOSS unavailable: '+' | '.join(nav))
        for h,e,team,rank in TARGETS:
            rec={'event_id':e,'selected_team':team,'tierb_rank':rank}
            try:
                host.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[h,e]); host.wait_for_timeout(5000)
                src=host.locator('#iframeDSTProps').get_attribute('src') or ''
            except Exception as ex:
                rec['host_error']=f'{type(ex).__name__}:{ex}'; results.append(rec); continue
            rec['iframe_present']=bool(src); rec['iframe_safe_path']=safe_url(src)
            if not src:
                results.append(rec); continue
            # token remains only in process memory; never written to output/logs.
            page=ctx.new_page(); caps=[]
            def onr(r):
                if 'digitalsportstech' not in r.url.lower() and 'bv2-us.' not in r.url.lower(): return
                try: body=r.text()
                except Exception: return
                if len(body)>3_000_000: body=body[:3_000_000]
                if relevant(body,team):
                    chunks=[]; seen=set()
                    pats=[re.escape(team),r'team\s*total',r'team\s*goals',r'handicap',r'double\s*chance',r'draw\s*no\s*bet',r'alternative',r'\+?1[\.,]5']
                    for pat in pats:
                        for m in re.finditer(pat,body,re.I):
                            a=max(0,m.start()-500); z=min(len(body),m.end()+900); s=redact(body[a:z])[:1800]
                            if s and s not in seen: seen.add(s); chunks.append(s)
                            if len(chunks)>=40: break
                        if len(chunks)>=40: break
                    caps.append({'url_path':safe_url(r.url),'status':r.status,'content_type':r.headers.get('content-type',''),'snippets':chunks})
            page.on('response',onr)
            try:
                resp=page.goto(src,wait_until='domcontentloaded',timeout=45000)
                rec['direct_status']=resp.status if resp else None
                page.wait_for_timeout(15000)
                try: text=c(page.locator('body').inner_text(timeout=15000))
                except Exception as ex: text=''; rec['body_error']=f'{type(ex).__name__}:{ex}'
                rec['body_text']=redact(text)[:80000]
                low=text.lower()
                rec['selected_team_mentioned']=team.lower() in low
                rec['plus15_literal']=bool(re.search(r'\+?1[\.,]5|\+1½',text))
                rec['team_total_literal']='team total' in low or 'team goals' in low or 'total por equipo' in low
                rec['double_chance_literal']='double chance' in low or 'doble oportunidad' in low
                rec['draw_no_bet_literal']='draw no bet' in low or 'empate no' in low
                try:
                    els=page.locator('button,[role=button],label,option,li,td,span,div').evaluate_all("""els=>els.map(x=>({tag:x.tagName,cls:typeof x.className==='string'?x.className:'',text:(x.innerText||x.textContent||'').replace(/\\s+/g,' ').trim()})).filter(x=>x.text&&x.text.length<=600)""")
                except Exception: els=[]
                keep=[]; seen=set()
                for x in els:
                    t=c(x.get('text'))
                    if not t or t in seen or not relevant(t,team): continue
                    seen.add(t); keep.append({'tag':x['tag'],'cls':c(x.get('cls')),'text':redact(t)})
                    if len(keep)>=300: break
                rec['relevant_visible_chunks']=keep
                rec['network_keyword_responses']=caps
            except Exception as ex:
                rec['direct_error']=f'{type(ex).__name__}:{ex}'
                rec['network_keyword_responses']=caps
            finally:
                try: page.remove_listener('response',onr)
                except Exception: pass
                page.close()
            results.append(rec)
        b.close()
    res={'captured_at_local':datetime.now(TZ).isoformat(),'nav_errors':nav,'results':results,'guard':'Read-only direct load of transient Advanced Props iframe URL. Sensitive query/token never persisted or logged; no bet click, coupon, wager, stake or account mutation.'}
    (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
    summ={'captured_at_local':res['captured_at_local'],'nav_errors':nav,'per_event':[{'rank':x['tierb_rank'],'event_id':x['event_id'],'team':x['selected_team'],'iframe_present':x.get('iframe_present'),'direct_status':x.get('direct_status'),'selected_team_mentioned':x.get('selected_team_mentioned'),'plus15_literal':x.get('plus15_literal'),'team_total_literal':x.get('team_total_literal'),'double_chance_literal':x.get('double_chance_literal'),'draw_no_bet_literal':x.get('draw_no_bet_literal'),'visible_chunks':len(x.get('relevant_visible_chunks',[])),'network_keyword_responses':len(x.get('network_keyword_responses',[])),'error':x.get('direct_error') or x.get('host_error')} for x in results]}
    (OUT/'summary.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(summ,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
