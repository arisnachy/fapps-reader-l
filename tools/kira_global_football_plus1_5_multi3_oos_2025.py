from __future__ import annotations

import csv, hashlib, io, json, math
from collections import Counter
from datetime import datetime, date
from pathlib import Path
import requests

OUT=Path('artifacts/kira_global_football_plus1_5_multi3_oos_2025'); OUT.mkdir(parents=True,exist_ok=True)
START=date(2024,12,27); END=date(2025,12,17)
EURO_SEASONS=['2425','2526']; EURO_LEAGUES=['E0','SP1','D1','I1','F1','N1','P1','SC0','B1']
SUMMER={'BRA':'https://www.football-data.co.uk/new/BRA.csv','USA':'https://www.football-data.co.uk/new/USA.csv'}
MIN_LEGS=100; MIN_DATES=100; MIN_LCB=.92

def wilson(w,n,z=1.959963984540054):
    if n<=0:return 0.0,1.0
    p=w/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
    return max(0,c-m),min(1,c+m)

def pdate(v):
    s=str(v).strip()
    for f in ('%d/%m/%y','%d/%m/%Y'):
        try:return datetime.strptime(s,f).date()
        except:pass
    return None

def decode(raw):
    for enc in ('utf-8-sig','latin-1'):
        try:return enc,list(csv.reader(io.StringIO(raw.decode(enc),newline='')))
        except:pass
    return '',[]

def write_csv(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    sess=requests.Session();sess.headers['User-Agent']='KIRA-GLOBAL-F15-M3-OOS2025/1.0'
    pre=[]; outcomes={}; audit=[]; seen=set(); dup=0

    # EUROPE_HOME. Outcome columns are stored in a separate map only; selector rows contain prematch fields only.
    req=['Date','HomeTeam','AwayTeam','B365H','B365D','B365A','FTHG','FTAG']
    for season in EURO_SEASONS:
      for lg in EURO_LEAGUES:
        url=f'https://www.football-data.co.uk/mmz4281/{season}/{lg}.csv'
        try:r=sess.get(url,timeout=45);r.raise_for_status()
        except Exception as exc:
            audit.append({'route':'EUROPE_HOME','season':season,'league':lg,'status':'SOURCE_UNUSABLE','reason':type(exc).__name__});continue
        raw=r.content;enc,rows=decode(raw);sha=hashlib.sha256(raw).hexdigest();header=None;hi=None
        for i,row in enumerate(rows):
            h=[str(x).strip() for x in row]
            if all(c in h for c in req):header=h;hi=i;break
        if header is None:
            audit.append({'route':'EUROPE_HOME','season':season,'league':lg,'status':'SOURCE_UNUSABLE','sha256':sha,'reason':'MISSING_COLUMNS'});continue
        idx={c:header.index(c) for c in req};mx=max(idx.values());eligible=0
        for row in rows[hi+1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']])
            if d is None or d<START or d>END:continue
            home=row[idx['HomeTeam']].strip();away=row[idx['AwayTeam']].strip()
            try:h=float(row[idx['B365H']]);dr=float(row[idx['B365D']]);a=float(row[idx['B365A']]);hg=int(float(row[idx['FTHG']]));ag=int(float(row[idx['FTAG']]))
            except:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h,dr,a)):continue
            qh,qd,qa=1/h,1/dr,1/a;ph=qh/(qh+qd+qa)
            if ph<.75:continue
            key=(d.isoformat(),'EUROPE_HOME',lg,home,away)
            if key in seen:dup+=1;continue
            seen.add(key);eid='G25E-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            pre.append({'date':d.isoformat(),'route':'EUROPE_HOME','source':season,'league':lg,'Home':home,'Away':away,'selected_side':'HOME','selected_entity':home,'selected_price':h,'signal_probability':ph,'event_id':eid})
            outcomes[eid]={'home_goals':hg,'away_goals':ag};eligible+=1
        audit.append({'route':'EUROPE_HOME','season':season,'league':lg,'status':'PASS','sha256':sha,'encoding':enc,'eligible_events':eligible})

    # SUMMER_FAVORITE, exact calendar year 2025 rows in common window.
    reqs=['Date','Home','Away','League','AvgCH','AvgCD','AvgCA','HG','AG']
    for code,url in SUMMER.items():
        r=sess.get(url,timeout=60);r.raise_for_status();raw=r.content;enc,rows=decode(raw);sha=hashlib.sha256(raw).hexdigest();h=[str(x).strip() for x in rows[0]]
        if not all(c in h for c in reqs):
            audit.append({'route':'SUMMER_FAVORITE','source':code,'status':'SOURCE_UNUSABLE','sha256':sha,'reason':'MISSING_COLUMNS'});continue
        idx={c:h.index(c) for c in reqs};mx=max(idx.values());eligible=0;target_serial=[]
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']])
            if d is None or d.year!=2025 or d<START or d>END:continue
            target_serial.append(','.join(row))
            home=row[idx['Home']].strip();away=row[idx['Away']].strip();lg=row[idx['League']].strip()
            try:h1=float(row[idx['AvgCH']]);dr=float(row[idx['AvgCD']]);a1=float(row[idx['AvgCA']]);hg=int(float(row[idx['HG']]));ag=int(float(row[idx['AG']]))
            except:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h1,dr,a1)):continue
            qh,qd,qa=1/h1,1/dr,1/a1;den=qh+qd+qa;ph,pa=qh/den,qa/den
            if ph==pa:continue
            side='HOME' if ph>pa else 'AWAY';prob=max(ph,pa)
            if prob<.60:continue
            ent=home if side=='HOME' else away;price=h1 if side=='HOME' else a1
            key=(d.isoformat(),'SUMMER_FAVORITE',code,lg,home,away)
            if key in seen:dup+=1;continue
            seen.add(key);eid='G25S-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            pre.append({'date':d.isoformat(),'route':'SUMMER_FAVORITE','source':code,'league':lg,'Home':home,'Away':away,'selected_side':side,'selected_entity':ent,'selected_price':price,'signal_probability':prob,'event_id':eid})
            outcomes[eid]={'home_goals':hg,'away_goals':ag};eligible+=1
        audit.append({'route':'SUMMER_FAVORITE','source':code,'status':'PASS','file_sha256':sha,'target_rows_sha256':hashlib.sha256('\n'.join(target_serial).encode()).hexdigest(),'target_rows':len(target_serial),'eligible_events':eligible})

    if dup:raise SystemExit(f'DUPLICATE_EVENT_KEYS={dup}')
    if any(x.get('status')!='PASS' for x in audit):
        s={'decision':'SOURCE_GATE_FAIL','source_audit':audit};(OUT/'summary.json').write_text(json.dumps(s,indent=2),encoding='utf-8');print(json.dumps(s,indent=2));return

    by={}
    for x in pre:by.setdefault(x['date'],[]).append(x)
    selected=[]
    for d,rows in sorted(by.items()):
        rows=sorted(rows,key=lambda x:(-x['signal_probability'],x['route'],x['selected_price'],x['source'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:3]
        for rank,x in enumerate(rows,1):selected.append({**x,'date_rank':rank})
    # Immutable pre-settlement ledger is written before outcome map is consulted.
    write_csv(OUT/'selected_event_keys_pre_settlement.csv',selected)
    ledger_sha=hashlib.sha256((OUT/'selected_event_keys_pre_settlement.csv').read_bytes()).hexdigest()

    settled=[]
    for x in selected:
        o=outcomes[x['event_id']]
        gd=(o['home_goals']-o['away_goals']) if x['selected_side']=='HOME' else (o['away_goals']-o['home_goals'])
        settled.append({**x,**o,'selected_goal_diff':gd,'hit':gd+1.5>0})
    write_csv(OUT/'selected_legs.csv',settled);write_csv(OUT/'failures.csv',[x for x in settled if not x['hit']])
    dates={}
    for x in settled:dates.setdefault(x['date'],[]).append(x)
    bundles=[]
    for d,rows in sorted(dates.items()):bundles.append({'date':d,'legs':len(rows),'survived':all(x['hit'] for x in rows),'event_ids':'|'.join(x['event_id'] for x in rows)})
    write_csv(OUT/'daily_bundles.csv',bundles);write_csv(OUT/'bundle_failures.csv',[x for x in bundles if not x['survived']])

    nl=len(settled);wl=sum(x['hit'] for x in settled);nd=len(bundles);wd=sum(x['survived'] for x in bundles);ll,_=wilson(wl,nl);dl,_=wilson(wd,nd)
    dist=Counter(x['legs'] for x in bundles);route=Counter(x['route'] for x in settled);failroute=Counter(x['route'] for x in settled if not x['hit'])
    summary={'hypothesis_id':'FOOTBALL_GLOBAL_PLUS1_5_MULTI3_2025_OOS','window':[START.isoformat(),END.isoformat()],'eligible_events_pre_global_cap':len(pre),'selected_legs':nl,'leg_wins':wl,'leg_losses':nl-wl,'leg_rate':wl/nl if nl else 0,'leg_wilson95_lcb':ll,'candidate_dates':nd,'bundle_wins':wd,'bundle_losses':nd-wd,'bundle_rate':wd/nd if nd else 0,'bundle_wilson95_lcb':dl,'date_leg_count_distribution':dict(sorted(dist.items())),'route_selected_counts':dict(route),'failure_route_counts':dict(failroute),'source_audit':audit,'selected_ledger_sha256':ledger_sha,'duplicate_event_keys':dup,'candidate_generation_used_outcomes':False,'leg_gate_pass':nl>=MIN_LEGS and ll>=MIN_LCB,'bundle_gate_pass':nd>=MIN_DATES and dl>=MIN_LCB}
    summary['decision']='OOS_CERTAINTY_PASS' if summary['leg_gate_pass'] and summary['bundle_gate_pass'] else 'NO_PASS'
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');(OUT/'source_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
