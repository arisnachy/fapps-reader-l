from __future__ import annotations

import asyncio,csv,hashlib,json,math,random,re
from collections import Counter,defaultdict
from datetime import date,datetime,timedelta
from pathlib import Path
from playwright.async_api import async_playwright

OUT=Path('artifacts/kira_max_2026_v2');OUT.mkdir(parents=True,exist_ok=True)
START=date(2026,1,1);END=date(2026,8,12);TH=0.60
NS=(3,4,5);MIN_DATES=35;OBS_FLOOR=0.90;WILSON_FLOOR=0.90
CONCURRENCY=3
DATE_RE=re.compile(r'^(\d{2} [A-Z][a-z]{2} 20\d{2})(?:\b|\s|\s-).*')
ROW_RE=re.compile(r'^(Finished|After ET|After Pen\.)\s+(\d+)\s+(.+?)\s+-\s+(.+?)\s+(\d+)\s+([0-9]+(?:\.[0-9]+)?|-)\s+([0-9]+(?:\.[0-9]+)?|-)\s+([0-9]+(?:\.[0-9]+)?|-)$')

def wilson(w,n,z=1.959963984540054):
    if n<=0:return 0.0,1.0
    p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
    return max(0,c-m),min(1,c+m)

def write_csv(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def daterange(a,b):
    d=a
    while d<=b:
        yield d;d+=timedelta(days=1)

def pdate_label(s):return datetime.strptime(s,'%d %b %Y').date()

def parse_texts(target,texts):
    competition=None;cur_date=None;pre=[];outcomes={};rows_seen=0;numeric_rows=0
    for raw in texts:
        t=' '.join(str(raw).split())
        if not t:continue
        if t.startswith('Football / '):
            competition=t;continue
        md=DATE_RE.match(t)
        if md:
            try:cur_date=pdate_label(md.group(1))
            except:cur_date=None
            continue
        mr=ROW_RE.match(t)
        if not mr:continue
        rows_seen+=1
        if cur_date!=target or not competition:continue
        status,hg_s,home,away,ag_s,oh_s,od_s,oa_s=mr.groups()
        if '-' in (oh_s,od_s,oa_s):continue
        try:oh,od,oa=map(float,(oh_s,od_s,oa_s));hg=int(hg_s);ag=int(ag_s)
        except:continue
        if not all(math.isfinite(x) and x>1.0 for x in (oh,od,oa)):continue
        numeric_rows+=1
        qh,qd,qa=1/oh,1/od,1/oa;den=qh+qd+qa
        if not math.isfinite(den) or den<=0:continue
        ph,pd,pa=qh/den,qd/den,qa/den
        side='HOME' if ph>pa else 'AWAY';prob=max(ph,pa)
        key=(target.isoformat(),competition,home,away)
        eid='MAXV2-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:24]
        outcomes[eid]={'status':status,'HG':hg,'AG':ag}
        if prob<TH:continue
        pre.append({'date':target.isoformat(),'competition':competition,'Home':home,'Away':away,'selected_side':side,
                    'selected_entity':home if side=='HOME' else away,'selected_1x2_price':oh if side=='HOME' else oa,
                    'odd_H':oh,'odd_D':od,'odd_A':oa,'p_home_novig':ph,'p_draw_novig':pd,'p_away_novig':pa,
                    'p_favorite_novig':prob,'event_id':eid})
    return pre,outcomes,{'parsed_result_rows':rows_seen,'numeric_target_rows':numeric_rows}

async def expand_show_more(page):
    clicks=0
    for _ in range(12):
        try:
            loc=page.get_by_text('SHOW MORE',exact=True)
            n=await loc.count();chosen=None
            for i in range(n):
                if await loc.nth(i).is_visible():chosen=loc.nth(i);break
            if chosen is None:break
            await chosen.click(timeout=3000);clicks+=1;await page.wait_for_timeout(450)
        except Exception:break
    return clicks

async def wait_for_historical_rows(page):
    await page.wait_for_function("""
      () => Array.from(document.querySelectorAll('div.border-black-borders'))
        .some(e => /^(Finished|After ET|After Pen\.)\s/.test((e.innerText || '').trim()))
    """, timeout=12000)

async def fetch_one(browser,target,sem):
    url=f'https://www.oddsportal.com/matches/football/{target.strftime("%Y%m%d")}/'
    async with sem:
        last=None
        for attempt in range(1,4):
            page=await browser.new_page(viewport={'width':1600,'height':1200},locale='en-US',timezone_id='UTC')
            try:
                await page.goto(url,wait_until='domcontentloaded',timeout=45000)
                await wait_for_historical_rows(page)
                await page.wait_for_timeout(350)
                clicks=await expand_show_more(page)
                texts=await page.locator('div.border-black-borders').evaluate_all('(els)=>els.map(e=>e.innerText.trim()).filter(Boolean)')
                body=await page.locator('body').inner_text(timeout=5000)
                resolved=page.url
                if 'Next Football Matches' not in body or len(body)<200:
                    raise RuntimeError('DATE_PAGE_NOT_LOADED')
                pre,outcomes,meta=parse_texts(target,texts)
                if meta['parsed_result_rows']<=0:
                    raise RuntimeError('NO_PARSED_RESULT_ROWS')
                await page.close()
                return {'date':target.isoformat(),'status':'PASS','requested_url':url,'resolved_url':resolved,'show_more_clicks':clicks,
                        'candidate_rows':pre,'outcomes':outcomes,**meta}
            except Exception as exc:
                last=f'{type(exc).__name__}:{exc}'
                try:await page.close()
                except:pass
                if attempt<3:await asyncio.sleep(0.8*attempt+random.random()*0.4)
        return {'date':target.isoformat(),'status':'FAIL','requested_url':url,'reason':last,'candidate_rows':[],'outcomes':{},
                'show_more_clicks':0,'parsed_result_rows':0,'numeric_target_rows':0}

async def scrape_all():
    dates=list(daterange(START,END));sem=asyncio.Semaphore(CONCURRENCY)
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        tasks=[asyncio.create_task(fetch_one(browser,d,sem)) for d in dates]
        results=[]
        for i,fut in enumerate(asyncio.as_completed(tasks),1):
            r=await fut;results.append(r)
            if i%10==0 or i==len(tasks):print(f'PROGRESS {i}/{len(tasks)} last={r["date"]} status={r["status"]}',flush=True)
        await browser.close()
    return sorted(results,key=lambda x:x['date'])

def score(results):
    failed_pages=[r for r in results if r['status']!='PASS']
    raw=[];outcomes={};page_audit=[]
    for r in results:
        raw.extend(r['candidate_rows']);outcomes.update(r['outcomes'])
        page_audit.append({k:v for k,v in r.items() if k not in ('candidate_rows','outcomes')})
    grouped=defaultdict(list)
    for x in raw:grouped[(x['date'],x['competition'],x['Home'],x['Away'])].append(x)
    pre=[];raw_dups=0;conflicts=[]
    for key,rr in grouped.items():
        rr=sorted(rr,key=lambda x:(x['odd_H'],x['odd_D'],x['odd_A'],x['event_id']))
        if len(rr)>1:
            raw_dups+=len(rr)-1
            sig={(x['odd_H'],x['odd_D'],x['odd_A']) for x in rr}
            if len(sig)>1:conflicts.append({'key':'|'.join(key),'variants':len(sig)})
        pre.append(rr[0])
    by=defaultdict(list)
    for x in pre:by[x['date']].append(x)
    frozen=[];calendar=[]
    for d in daterange(START,END):
        ds=d.isoformat();rr=sorted(by.get(ds,[]),key=lambda x:(-x['p_favorite_novig'],x['selected_1x2_price'],x['competition'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))
        for rank,x in enumerate(rr[:5],1):frozen.append({**x,'date_rank':rank,'eligible_count_on_date':len(rr)})
        calendar.append({'date':ds,'eligible_count':len(rr),'T3_available':len(rr)>=3,'T4_available':len(rr)>=4,'T5_available':len(rr)>=5})
    write_csv(OUT/'rank1_5_pre_settlement.csv',frozen)
    ledger_sha=hashlib.sha256((OUT/'rank1_5_pre_settlement.csv').read_bytes()).hexdigest()
    settled=[];unresolved=[]
    for x in frozen:
        o=outcomes.get(x['event_id'])
        if not o:
            row={**x,'source_status':None,'HG':None,'AG':None,'selected_goal_diff':None,'hit':None};unresolved.append(row)
        elif o['status'] in ('After ET','After Pen.'):
            row={**x,'source_status':o['status'],'HG':o['HG'],'AG':o['AG'],'selected_goal_diff':'REG_TIED','hit':True}
        elif o['status']=='Finished':
            gd=(o['HG']-o['AG']) if x['selected_side']=='HOME' else (o['AG']-o['HG'])
            row={**x,'source_status':o['status'],'HG':o['HG'],'AG':o['AG'],'selected_goal_diff':gd,'hit':bool(gd+1.5>0)}
        else:
            row={**x,'source_status':o.get('status'),'HG':o.get('HG'),'AG':o.get('AG'),'selected_goal_diff':None,'hit':None};unresolved.append(row)
        settled.append(row)
    write_csv(OUT/'rank1_5_settled.csv',settled);write_csv(OUT/'unresolved_ranked.csv',unresolved);write_csv(OUT/'calendar.csv',calendar);write_csv(OUT/'date_page_audit.csv',page_audit)
    sd=defaultdict(list)
    for x in settled:sd[x['date']].append(x)
    for d in sd:sd[d]=sorted(sd[d],key=lambda x:x['date_rank'])
    per_n={};all_fail=[]
    for n in NS:
        tickets=[]
        for c in calendar:
            if c['eligible_count']<n:continue
            rr=sd[c['date']][:n]
            if len(rr)!=n:raise RuntimeError(f'PREFIX_MISMATCH {c["date"]} N{n}')
            unr=any(x['hit'] is None for x in rr);surv=None if unr else all(bool(x['hit']) for x in rr)
            t={'date':c['date'],'N':n,'status':'UNRESOLVED' if unr else ('WIN' if surv else 'LOSS'),'survived':surv,
               'entities':'|'.join(x['selected_entity'] for x in rr),'competitions':'|'.join(x['competition'] for x in rr),'event_ids':'|'.join(x['event_id'] for x in rr)}
            tickets.append(t)
            if surv is False:all_fail.append(t)
        ev=[x for x in tickets if x['survived'] is not None];wins=sum(x['survived'] is True for x in ev);total=len(ev);l,u=wilson(wins,total);rate=wins/total if total else 0.0
        per_n[str(n)]={'N':n,'available_dates':len(tickets),'evaluable_dates':total,'unresolved_dates':len(tickets)-total,'ticket_wins':wins,
                       'ticket_losses':total-wins,'ticket_survival':rate,'ticket_wilson95_lcb':l,'ticket_wilson95_ucb':u,
                       'certainty_pass':total>=MIN_DATES and rate>OBS_FLOOR and l>=WILSON_FLOOR}
        write_csv(OUT/f'tickets_T{n}.csv',tickets)
    total_days=len(calendar);c3=sum(x['T3_available'] for x in calendar);f5=sum(x['T5_available'] for x in calendar)
    availability={'calendar_days':total_days,'core3_days':c3,'core3_rate':c3/total_days,'full_stack_days':f5,'full_stack_rate':f5/total_days,'daily_availability_pass':f5==total_days}
    integrity=(not failed_pages and not conflicts and not unresolved)
    certainty_all=all(per_n[str(n)]['certainty_pass'] for n in NS)
    if failed_pages:decision='EVIDENCE_INCOMPLETE_DO_NOT_PIN'
    else:decision='PIN_MAX_2026_V2_PASS' if integrity and availability['daily_availability_pass'] and certainty_all else 'NO_PASS_DO_NOT_PIN'
    dist=Counter(min(x['eligible_count'],20) for x in calendar)
    res={'hypothesis_id':'MAX_2026_V2_UNIVERSAL','status':'COMPLETED_2026_THROUGH_AUG12_RETROSPECTIVE','decision':decision,
         'calendar_start':START.isoformat(),'calendar_end':END.isoformat(),'threshold':TH,'candidate_generation_used_outcomes':False,
         'pre_settlement_ledger_sha256':ledger_sha,'date_pages_attempted':len(results),'date_pages_pass':len(results)-len(failed_pages),'date_pages_failed':len(failed_pages),
         'failed_dates':[x['date'] for x in failed_pages],'raw_duplicate_rows':raw_dups,'conflicting_duplicate_events':len(conflicts),'duplicate_event_keys_after_dedup':0,
         'unresolved_ranked_legs':len(unresolved),'integrity_gate_pass':integrity,'availability':availability,'per_n':per_n,
         'eligible_count_distribution_capped20':dict(sorted(dist.items())),'total_eligible_candidates':len(pre)}
    write_csv(OUT/'failed_tickets.csv',all_fail);write_csv(OUT/'duplicate_conflicts.csv',conflicts)
    (OUT/'summary.json').write_text(json.dumps(res,indent=2),encoding='utf-8')
    print('FINAL_SUMMARY');print(json.dumps(res,indent=2),flush=True)
    return res

async def main():
    results=await scrape_all();score(results)

if __name__=='__main__':asyncio.run(main())
