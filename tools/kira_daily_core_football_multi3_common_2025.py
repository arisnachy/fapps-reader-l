from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

OUT=Path('artifacts/kira_daily_core_football_multi3_common_2025')
LEAGUES=['E0','SP1','D1','I1','F1','N1','P1','SC0','B1']
SEASONS=['2425','2526']
START=date(2024,12,27); END=date(2025,12,17)
REQ=['Date','HomeTeam','AwayTeam','B365H','B365D','B365A']

def parse_date(v):
    s=str(v).strip()
    for f in ('%d/%m/%y','%d/%m/%Y'):
        try:return datetime.strptime(s,f).date()
        except ValueError:pass
    return None

def event_id(r):
    payload='|'.join([r['date'],r['league_code'],r['HomeTeam'],r['AwayTeam']])
    return 'FHIST-'+hashlib.sha256(payload.encode()).hexdigest()[:20]

def write_csv(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    s=requests.Session();s.headers['User-Agent']='KIRA-MULTI3-common-coverage/1.0'
    rows=[]; audit=[]
    for season in SEASONS:
        for lg in LEAGUES:
            url=f'https://www.football-data.co.uk/mmz4281/{season}/{lg}.csv'
            r=s.get(url,timeout=30); r.raise_for_status(); raw=r.content; sha=hashlib.sha256(raw).hexdigest()
            frame=None;enc=''
            for e in ('utf-8-sig','latin-1'):
                try:frame=pd.read_csv(io.BytesIO(raw),encoding=e);enc=e;break
                except UnicodeDecodeError:pass
            if frame is None:raise SystemExit(f'UNREADABLE {url}')
            miss=[c for c in REQ if c not in frame.columns]
            if miss:raise SystemExit(f'MISSING {url} {miss}')
            accepted=0
            for _,x in frame.iterrows():
                d=parse_date(x['Date'])
                if not d or not(START<=d<=END):continue
                try:h=float(x['B365H']);dr=float(x['B365D']);a=float(x['B365A'])
                except:continue
                if not all(math.isfinite(v) and v>1 for v in (h,dr,a)):continue
                home=str(x['HomeTeam']).strip();away=str(x['AwayTeam']).strip()
                if not home or not away or home.lower()=='nan' or away.lower()=='nan':continue
                qh,qd,qa=1/h,1/dr,1/a;ph=qh/(qh+qd+qa)
                rows.append({'date':d.isoformat(),'season':season,'league_code':lg,'HomeTeam':home,'AwayTeam':away,'B365H':h,'B365D':dr,'B365A':a,'p_home_novig':ph})
                accepted+=1
            audit.append({'season':season,'league':lg,'url':url,'sha256':sha,'bytes':len(raw),'raw_rows':len(frame),'accepted_window_rows':accepted,'encoding':enc})
    keys=[(r['date'],r['league_code'],r['HomeTeam'],r['AwayTeam']) for r in rows]
    dup=[k for k,n in Counter(keys).items() if n>1]
    if dup:raise SystemExit(f'DUPLICATE_EVENTS {len(dup)}')

    by_date={}
    for r in rows:
        if r['p_home_novig']>=.75:by_date.setdefault(r['date'],[]).append(r)
    selected=[]
    for d,items in sorted(by_date.items()):
        top=sorted(items,key=lambda x:(-x['p_home_novig'],x['B365H'],x['league_code'],x['HomeTeam'],x['AwayTeam']))[:3]
        for rank,x in enumerate(top,1):
            selected.append({**x,'event_id':event_id(x),'date_rank':rank,'strategy_id':'FOOTBALL_PLUS1_5_MARKET_DOMINANCE_MULTI3_V1','sport':'football','selected_entity':x['HomeTeam'],'opponent':x['AwayTeam'],'frozen_line':1.5,'science_state':'SCIENCE/CERTAINTY PASS','sports_candidate_frozen':True})
    write_csv(OUT/'multi3_candidates.csv',selected)
    (OUT/'source_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    counts=Counter(r['date'] for r in selected)
    daily=[];cur=START
    while cur<=END:
        d=cur.isoformat();daily.append({'date':d,'multi3_legs':counts.get(d,0)});cur+=timedelta(days=1)
    write_csv(OUT/'daily_counts.csv',daily)
    summary={'window_start':START.isoformat(),'window_end':END.isoformat(),'calendar_days':len(daily),'pregame_rows':len(rows),'eligible_events_before_cap':sum(len(v) for v in by_date.values()),'selected_legs':len(selected),'candidate_dates':len(counts),'date_leg_count_distribution':dict(sorted(Counter(counts.values()).items())),'max_legs_date':max(counts.values()) if counts else 0,'outcomes_loaded_or_used':False,'source_files':len(audit),'duplicate_events':len(dup)}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
