from __future__ import annotations
import csv, html, io, json, re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_full_universe_rule_intersection_v10')
TZ=ZoneInfo('America/Santo_Domingo')

def c(x): return re.sub(r'\s+',' ',str(x or '').replace('\xa0',' ')).strip()
def norm(s): return html.unescape(str(s or '')).replace("\\'", "'").replace('\\n','\n').replace('\\r','')
def adec(a):
    a=float(a)
    return 1+a/100 if a>0 else 1+100/abs(a) if a<0 else None

def split_args(raw):
    # Constructor args are simple JS literals in BOSS schedule payloads. CSV parsing handles quoted labels.
    try:
        return next(csv.reader(io.StringIO(raw), skipinitialspace=True, quotechar="'", escapechar='\\'))
    except Exception:
        return []

def parse_events(body,label):
    s=norm(body); starts=list(re.finditer(r'newE\s*=\s*new\s+Event\((.*?)\);',s,re.S)); out=[]
    for i,m in enumerate(starts):
        raw=m.group(1); args=split_args(raw)
        if len(args)<38: continue
        try:
            hid=int(str(args[0]).strip()); eid=int(str(args[1]).strip()); title=c(str(args[2]).strip("'\""))
            y,mo,d,hh,mm=[int(float(str(args[j]).strip())) for j in range(3,8)]
            league_id=int(float(str(args[8]).strip())); sport_type=int(float(str(args[9]).strip()))
            sport_name=c(str(args[37]).strip("'\""))
        except Exception: continue
        if sport_type!=4 and sport_name.lower()!='soccer': continue
        end=starts[i+1].start() if i+1<len(starts) else min(len(s),m.end()+16000); block=s[m.end():end]
        parts={}
        rx=re.compile(r"newP\s*=\s*new\s+Participant\(\s*(\d+)\s*,\s*([123])\s*,\s*'([^']*)'\s*,\s*'[^']*'\s*,\s*'[^']*'\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)",re.S)
        for q in rx.finditer(block):
            if int(q.group(1))==eid:
                parts[int(q.group(2))]={'name':c(q.group(3)),'ml':float(q.group(4)),'spread':float(q.group(5)),'spread_price':float(q.group(6))}
        ev={'menu':label,'header_id':hid,'event_id':eid,'title':title,'date':f'{y:04d}-{mo:02d}-{d:02d}','time':f'{hh:02d}:{mm:02d}','league_id':league_id,'sport_type':sport_type,'sport_name':sport_name,'parts':parts}
        if all(k in parts and parts[k]['ml']!=0 for k in (1,2,3)) and len({parts[k]['ml'] for k in (1,2,3)})>1:
            ds={k:adec(parts[k]['ml']) for k in (1,2,3)}; inv={k:1/ds[k] for k in ds}; z=sum(inv.values())
            ev['p_home_novig']=inv[1]/z; ev['p_away_novig']=inv[3]/z
        out.append(ev)
    return out

def dom_ml(page,label):
    try:
        rows=page.locator("[id^='ML_'],[id^='SZML_']").evaluate_all("els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),cls:typeof e.className==='string'?e.className:'',title:e.getAttribute('title')||''}))")
    except Exception: return []
    out=[]
    for x in rows:
        m=re.match(r'^(?:SZ)?ML_(\d+)_([123])$',x['id'],re.I)
        if m:
            out.append({'menu':label,'event_id':int(m.group(1)),'sel':int(m.group(2)),'id':x['id'],'text':c(x['text']),'cls':c(x['cls']),'title':c(x['title']),'actionable':'tooltip_addBet' in x['cls'] and 'cellCandado' not in x['cls']})
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True); now=datetime.now(TZ); current={'label':'initial'}; net=[]; markets=[]; nav_errors=[]; r=None
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True); page=b.new_page(viewport={'width':1600,'height':1800},locale='es-DO',timezone_id='America/Santo_Domingo')
        def resp(rsp):
            if 'juancitosport.com.do' not in rsp.url or rsp.request.resource_type not in {'xhr','fetch'}: return
            if '_method=RefreshSelectedHeader' not in rsp.url and '_method=GetUpcomingEvents' not in rsp.url: return
            try: body=rsp.text()
            except Exception: return
            evs=parse_events(body,current['label'])
            if evs: net.extend(evs)
        page.on('response',resp)
        for attempt in range(1,4):
            try:
                r=page.goto(START,wait_until='commit',timeout=45000); page.wait_for_timeout(14000)
                if page.locator('#tblSH_53').count(): break
                nav_errors.append(f'attempt {attempt}: tblSH_53 missing; url={page.url}')
            except Exception as ex: nav_errors.append(f'attempt {attempt}: {type(ex).__name__}: {ex}')
            try: page.wait_for_timeout(3000)
            except Exception: pass
        if not page.locator('#tblSH_53').count():
            b.close(); raise RuntimeError('BOSS soccer menu not loaded: '+' | '.join(nav_errors))
        points=page.evaluate("""()=>{const p=(window.WagerSession&&WagerSession.PointsRule)||null; if(!p)return {has:false,buy:[],sell:[]}; const pack=(a,kind)=>(a||[]).map(x=>({LeagueId:Number(x.LeagueId),PointId:Number(kind==='buy'?x.BuyPointId:x.SellPointId),OddsToLay:Number(x.OddsToLay),OddsToTake:Number(x.OddsToTake)})); return {has:true,buy:pack(p.BuyDetails,'buy'),sell:pack(p.SellDetails,'sell')};}""")
        subs=page.locator('#tblSH_53 .colSubHeader').evaluate_all("els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),visible:!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)}))")
        attempts=[]
        for s in subs:
            if not re.match(r'^shdr\d+$',s['id']): continue
            current['label']=s['text']; rec={**s,'clicked':False}
            try:
                page.locator('#'+s['id']).click(force=True,timeout=7000); rec['clicked']=True; page.wait_for_timeout(1800); markets.extend(dom_ml(page,s['text']))
            except Exception as ex: rec['error']=f'{type(ex).__name__}:{ex}'
            attempts.append(rec)
        b.close()
    ev={}
    for x in net: ev[x['event_id']]=x
    events=list(ev.values()); ml_by=defaultdict(dict)
    for x in markets: ml_by[x['event_id']][x['sel']]=x
    actionable=[]
    for x in events:
        cells=ml_by.get(x['event_id'],{}); x['ml_cells']=cells; x['complete_actionable_1x2']=all(k in cells and cells[k]['actionable'] for k in (1,2,3))
        if x['complete_actionable_1x2']: actionable.append(x)
    buy_leagues=sorted({int(x['LeagueId']) for x in points.get('buy',[])})
    sell_leagues=sorted({int(x['LeagueId']) for x in points.get('sell',[])})
    actionable_leagues=Counter(int(x['league_id']) for x in actionable)
    intersection=sorted(set(actionable_leagues)&set(buy_leagues))
    inter_events=[x for x in actionable if int(x['league_id']) in intersection]
    by_buy=defaultdict(list)
    for x in points.get('buy',[]): by_buy[int(x['LeagueId'])].append(x)
    inter_rules={str(l):by_buy[l] for l in intersection}
    summary={
      'captured_at_local':now.isoformat(),'http':r.status if r else None,'nav_errors':nav_errors,
      'subheaders_discovered':len(subs),'subheaders_attempted':len(attempts),'all_clicked':bool(attempts) and all(x.get('clicked') for x in attempts),
      'soccer_events_seen_unique':len(events),'complete_actionable_1x2_events':len(actionable),
      'actionable_league_ids':dict(sorted(actionable_leagues.items())),
      'points_rule_present':bool(points.get('has')),'points_buy_league_ids':buy_leagues,'points_sell_league_ids':sell_leagues,
      'football_buy_rule_intersection_league_ids':intersection,'football_buy_rule_intersection_event_count':len(inter_events),
      'coverage_complete_public_menu':bool(attempts) and all(x.get('clicked') for x in attempts),
      'guard':'Read-only full public Football traversal + in-memory rule inspection. No bet selection, coupon, stake or account mutation.'
    }
    result={**summary,'football_menu_subheaders':subs,'menu_attempts':attempts,'points_rule':points,'intersection_rules':inter_rules,'intersection_events':inter_events,'events':events}
    (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
