from __future__ import annotations

import csv, io, json, hashlib, math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
import requests

OUT = Path('artifacts/kira_max_2026_v1'); OUT.mkdir(parents=True, exist_ok=True)
START=date(2026,1,1); END=date(2026,8,12)
TH=0.60; NS=(3,4,5); MIN_DATES=35; OBS_FLOOR=0.90; WILSON_FLOOR=0.90
MAIN_CODES=['E0','E1','E2','E3','E4','SC0','SC1','SC2','SC3','D1','D2','I1','I2','SP1','SP2','F1','F2','N1','B1','P1','T1','G1']
EXTRA_CODES=['ARG','AUT','BRA','CHN','DNK','FIN','IRL','JPN','MEX','NOR','POL','ROU','RUS','SWE','SWZ','USA']


def wilson(w,n,z=1.959963984540054):
    if n<=0:return (0.0,1.0)
    p=w/n; d=1+z*z/n; c=(p+z*z/(2*n))/d
    m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
    return max(0,c-m),min(1,c+m)

def pdate(s):
    s=str(s).strip()
    for f in ('%d/%m/%Y','%d/%m/%y','%Y-%m-%d'):
        try:return datetime.strptime(s,f).date()
        except Exception:pass
    return None

def write_csv(path, rows):
    if not rows:
        path.write_text('',encoding='utf-8'); return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def choose_cols(h):
    if all(c in h for c in ('AvgCH','AvgCD','AvgCA')):
        return ('AvgCH','AvgCD','AvgCA','CLOSING_AVG')
    if all(c in h for c in ('AvgH','AvgD','AvgA')):
        return ('AvgH','AvgD','AvgA','PREMATCH_AVG')
    return None

def parse_source(sess,label,url,source_kind,required=False):
    try:
        r=sess.get(url,timeout=45); status=r.status_code
        if status!=200:
            return [],{}, {'source':label,'url':url,'status':'UNAVAILABLE','http_status':status,'required':required}
        raw=r.content
    except Exception as exc:
        return [],{}, {'source':label,'url':url,'status':'UNAVAILABLE','reason':type(exc).__name__,'required':required}
    text=raw.decode('utf-8-sig',errors='replace')
    rows=list(csv.reader(io.StringIO(text)))
    if not rows or len(rows[0])<5:
        return [],{}, {'source':label,'url':url,'status':'UNUSABLE','reason':'EMPTY_OR_NONCSV','required':required}
    h=[x.strip() for x in rows[0]]; idx={k:i for i,k in enumerate(h)}
    odds=choose_cols(h)
    home_col='HomeTeam' if 'HomeTeam' in idx else ('Home' if 'Home' in idx else None)
    away_col='AwayTeam' if 'AwayTeam' in idx else ('Away' if 'Away' in idx else None)
    hg_col='FTHG' if 'FTHG' in idx else ('HG' if 'HG' in idx else None)
    ag_col='FTAG' if 'FTAG' in idx else ('AG' if 'AG' in idx else None)
    date_col='Date' if 'Date' in idx else None
    if not odds or not all((date_col,home_col,away_col,hg_col,ag_col)):
        return [],{}, {'source':label,'url':url,'status':'UNUSABLE','reason':'MISSING_REQUIRED_COLUMNS','headers':h[:40],'required':required}
    oh,od,oa,odds_family=odds
    pre=[]; outcomes={}; target_rows=0; eligible=0; malformed=0
    for row in rows[1:]:
        if len(row)<len(h): row=row+['']*(len(h)-len(row))
        d=pdate(row[idx[date_col]])
        if d is None or d<START or d>END: continue
        target_rows+=1
        home=row[idx[home_col]].strip(); away=row[idx[away_col]].strip()
        if not home or not away: malformed+=1; continue
        try:
            ho=float(row[idx[oh]]); do=float(row[idx[od]]); ao=float(row[idx[oa]])
            if not all(math.isfinite(x) and x>1.0 for x in (ho,do,ao)): raise ValueError
        except Exception:
            continue
        qh,qd,qa=1/ho,1/do,1/ao; den=qh+qd+qa
        ph,pa=qh/den,qa/den
        if ph==pa: continue
        side='HOME' if ph>pa else 'AWAY'; prob=max(ph,pa)
        if prob<TH: continue
        selected_entity=home if side=='HOME' else away
        selected_price=ho if side=='HOME' else ao
        division=(row[idx['Div']].strip() if 'Div' in idx and row[idx['Div']].strip() else label)
        key=(d.isoformat(),label,division,home,away)
        eid='MAX26-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:24]
        pre.append({'date':d.isoformat(),'source':label,'source_kind':source_kind,'division':division,'Home':home,'Away':away,
                    'selected_side':side,'selected_entity':selected_entity,'selected_1x2_price':selected_price,
                    'p_favorite_novig':prob,'odds_family':odds_family,'event_id':eid})
        try:hg=int(float(row[idx[hg_col]]));ag=int(float(row[idx[ag_col]]));outcomes[eid]={'HG':hg,'AG':ag,'settled':True}
        except Exception:outcomes[eid]={'HG':None,'AG':None,'settled':False}
        eligible+=1
    audit={'source':label,'url':url,'status':'PASS','required':required,'file_sha256':hashlib.sha256(raw).hexdigest(),
           'target_rows':target_rows,'eligible_pre_rank':eligible,'malformed_target_rows':malformed,'odds_family':odds_family}
    return pre,outcomes,audit

def main():
    sess=requests.Session(); sess.headers['User-Agent']='KIRA-MAX-2026-V1/1.0'
    all_pre=[]; outcomes={}; audit=[]
    # Main 2025/26 is required. 2026/27 is optional because publication may not yet exist for every division.
    for season,required in [('2526',True),('2627',False)]:
        for code in MAIN_CODES:
            label=f'MAIN{season}:{code}'; url=f'https://www.football-data.co.uk/mmz4281/{season}/{code}.csv'
            pre,o,a=parse_source(sess,label,url,'MAIN',required); all_pre.extend(pre); outcomes.update(o); audit.append(a)
    for code in EXTRA_CODES:
        label=f'EXTRA:{code}'; url=f'https://www.football-data.co.uk/new/{code}.csv'
        pre,o,a=parse_source(sess,label,url,'EXTRA',True); all_pre.extend(pre); outcomes.update(o); audit.append(a)

    required_bad=[a for a in audit if a.get('required') and a.get('status')!='PASS']
    # Deduplicate exact event identity across source-season representations only when home/away/date are identical.
    seen=set(); dedup=[]; dup_rows=[]
    for x in sorted(all_pre,key=lambda x:(x['date'],x['source'],x['division'],x['Home'],x['Away'])):
        natural=(x['date'],x['source'],x['division'],x['Home'],x['Away'])
        if natural in seen: dup_rows.append(x); continue
        seen.add(natural); dedup.append(x)
    all_pre=dedup

    by=defaultdict(list)
    for x in all_pre:by[x['date']].append(x)
    frozen=[]; eligible_counts={}
    day=START
    calendar=[]
    while day<=END:
        ds=day.isoformat(); rr=by.get(ds,[])
        rr=sorted(rr,key=lambda x:(-x['p_favorite_novig'],x['selected_1x2_price'],x['source'],x['division'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))
        eligible_counts[ds]=len(rr)
        for rank,x in enumerate(rr[:5],1): frozen.append({**x,'date_rank':rank,'eligible_count_on_date':len(rr)})
        calendar.append({'date':ds,'eligible_count':len(rr),'T3_available':len(rr)>=3,'T4_available':len(rr)>=4,'T5_available':len(rr)>=5})
        day+=timedelta(days=1)

    write_csv(OUT/'rank1_5_pre_settlement.csv',frozen)
    ledger_sha=hashlib.sha256((OUT/'rank1_5_pre_settlement.csv').read_bytes()).hexdigest()
    settled=[]; unresolved=[]
    for x in frozen:
        o=outcomes.get(x['event_id'],{'settled':False,'HG':None,'AG':None})
        if not o.get('settled'):
            row={**x,'HG':None,'AG':None,'selected_goal_diff':None,'hit':None}; unsettled=True
            unresolved.append(row)
        else:
            gd=(o['HG']-o['AG']) if x['selected_side']=='HOME' else (o['AG']-o['HG'])
            row={**x,'HG':o['HG'],'AG':o['AG'],'selected_goal_diff':gd,'hit':bool(gd+1.5>0)}
        settled.append(row)
    write_csv(OUT/'rank1_5_settled.csv',settled); write_csv(OUT/'unresolved.csv',unresolved); write_csv(OUT/'calendar.csv',calendar)
    sd=defaultdict(list)
    for x in settled:sd[x['date']].append(x)
    for d in sd:sd[d]=sorted(sd[d],key=lambda x:x['date_rank'])

    per_n={}; failures=[]
    for n in NS:
        tickets=[]
        for c in calendar:
            d=c['date']
            if eligible_counts[d]<n: continue
            rr=sd[d][:n]
            if len(rr)!=n: raise RuntimeError(f'prefix mismatch {d} N={n}')
            unresolved_ticket=any(x['hit'] is None for x in rr)
            survived=None if unresolved_ticket else all(bool(x['hit']) for x in rr)
            t={'date':d,'N':n,'status':'UNRESOLVED' if unresolved_ticket else ('WIN' if survived else 'LOSS'),
               'survived':survived,'entities':'|'.join(x['selected_entity'] for x in rr),'event_ids':'|'.join(x['event_id'] for x in rr)}
            tickets.append(t)
            if survived is False:failures.append(t)
        evaluable=[t for t in tickets if t['survived'] is not None]
        wins=sum(t['survived'] is True for t in evaluable); total=len(evaluable); lcb,ucb=wilson(wins,total); rate=wins/total if total else 0.0
        per_n[str(n)]={'N':n,'available_dates':len(tickets),'evaluable_dates':total,'unresolved_dates':len(tickets)-total,
                       'ticket_wins':wins,'ticket_losses':total-wins,'ticket_survival':rate,'ticket_wilson95_lcb':lcb,'ticket_wilson95_ucb':ucb,
                       'certainty_pass': total>=MIN_DATES and rate>OBS_FLOOR and lcb>=WILSON_FLOOR}
        write_csv(OUT/f'tickets_T{n}.csv',tickets)

    cal_n=len(calendar); core3=sum(c['T3_available'] for c in calendar); full5=sum(c['T5_available'] for c in calendar)
    availability={'calendar_days':cal_n,'core3_days':core3,'core3_rate':core3/cal_n,'full_stack_days':full5,'full_stack_rate':full5/cal_n,
                  'daily_availability_pass':full5==cal_n}
    count_dist=Counter(min(c['eligible_count'],10) for c in calendar)
    unresolved_count=len(unresolved)
    source_gate=(len(required_bad)==0)
    integrity_gate=(len(dup_rows)==0 and unresolved_count==0)
    certainty_all=all(per_n[str(n)]['certainty_pass'] for n in NS)
    decision='PIN_MAX_2026_V1_PASS' if source_gate and integrity_gate and availability['daily_availability_pass'] and certainty_all else 'NO_PASS_DO_NOT_PIN'
    res={'hypothesis_id':'MAX_2026_V1','status':'COMPLETED_2026_THROUGH_AUG12_RETROSPECTIVE','decision':decision,
         'calendar_start':START.isoformat(),'calendar_end':END.isoformat(),'threshold':TH,
         'candidate_generation_used_outcomes':False,'duplicate_event_keys':len(dup_rows),'pre_settlement_ledger_sha256':ledger_sha,
         'source_gate_pass':source_gate,'required_source_failures':required_bad,'integrity_gate_pass':integrity_gate,'unresolved_ranked_legs':unresolved_count,
         'availability':availability,'per_n':per_n,'eligible_count_distribution_capped10':dict(sorted(count_dist.items())),
         'usable_sources':sum(a['status']=='PASS' for a in audit),'total_source_attempts':len(audit),'source_audit':audit}
    write_csv(OUT/'failed_tickets.csv',failures); write_csv(OUT/'source_audit.csv',audit)
    (OUT/'summary.json').write_text(json.dumps(res,indent=2),encoding='utf-8')
    print(json.dumps(res,indent=2))

if __name__=='__main__':main()
