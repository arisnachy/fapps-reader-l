from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime, date, timedelta
from pathlib import Path

import requests

OUT=Path('artifacts/kira_football_multi3_common_2025')
T3_LEDGER=Path('data/TENNIS_T3_COVERAGE_ROWS_2025.csv')
LEAGUES=['E0','SP1','D1','I1','F1','N1','P1','SC0','B1']
SEASONS=['2425','2526']
REQ=['Date','HomeTeam','AwayTeam','B365H','B365D','B365A']
START=date(2024,12,27); END=date(2025,12,17)


def parse_date(x):
    s=str(x).strip()
    for f in ('%d/%m/%y','%d/%m/%Y'):
        try:return datetime.strptime(s,f).date()
        except Exception: pass
    return None

def write_csv(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)

def decode_rows(raw):
    for enc in ('utf-8-sig','latin-1'):
        try:return enc,list(csv.reader(io.StringIO(raw.decode(enc),newline='')))
        except Exception:pass
    return '',[]

def event_id(r):
    key='|'.join([r['date'],r['league_code'],r['HomeTeam'],r['AwayTeam']])
    return 'FMOD-'+hashlib.sha256(key.encode()).hexdigest()[:20]

def longest_red(rows):
    best=[];cur=[]
    for r in rows:
        if r['total_candidate_legs']<3:
            cur.append(r)
            if len(cur)>len(best):best=list(cur)
        else:cur=[]
    return {'days':len(best),'start':best[0]['date'] if best else None,'end':best[-1]['date'] if best else None}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    s=requests.Session();s.headers['User-Agent']='KIRA-MULTI3-common-calendar/1.1'
    audit=[]; valid=[]; seen=set()
    for season in SEASONS:
      for lg in LEAGUES:
        url=f'https://www.football-data.co.uk/mmz4281/{season}/{lg}.csv'
        try:r=s.get(url,timeout=30)
        except Exception as e:
            audit.append({'season':season,'league':lg,'status':'SOURCE_UNUSABLE','reason':type(e).__name__});continue
        if r.status_code!=200:
            audit.append({'season':season,'league':lg,'status':'SOURCE_UNUSABLE','http':r.status_code});continue
        raw=r.content; enc,rows=decode_rows(raw); sha=hashlib.sha256(raw).hexdigest()
        header=None;hi=None
        for i,row in enumerate(rows):
            clean=[str(x).strip() for x in row]
            if all(c in clean for c in REQ):header=clean;hi=i;break
        if header is None:
            audit.append({'season':season,'league':lg,'status':'SOURCE_UNUSABLE','reason':'MISSING_REQUIRED','sha256':sha});continue
        idx={c:header.index(c) for c in REQ}; mx=max(idx.values());accepted=0
        for row in rows[hi+1:]:
            if len(row)<=mx:continue
            vals={c:row[j] for c,j in idx.items()}; d=parse_date(vals['Date'])
            if d is None or d<START or d>END:continue
            home=str(vals['HomeTeam']).strip();away=str(vals['AwayTeam']).strip()
            try:h=float(vals['B365H']);dr=float(vals['B365D']);a=float(vals['B365A'])
            except Exception:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h,dr,a)):continue
            key=(d.isoformat(),lg,home,away)
            if key in seen:continue
            seen.add(key)
            qh,qd,qa=1/h,1/dr,1/a; den=qh+qd+qa; ph=qh/den; pa=qa/den
            item={'date':d.isoformat(),'season':season,'league_code':lg,'HomeTeam':home,'AwayTeam':away,'B365H':h,'B365D':dr,'B365A':a,'p_home_novig':ph,'p_away_novig':pa}
            item['event_id']=event_id(item);valid.append(item);accepted+=1
        audit.append({'season':season,'league':lg,'status':'PASS','sha256':sha,'bytes':len(raw),'encoding':enc,'valid_in_window':accepted})

    # Scientifically PASS MULTI3 HOME +1.5: up to 3 HOME events/date at p_home>=.75.
    home_by={}
    for r in valid:
        if r['p_home_novig']>=.75:home_by.setdefault(r['date'],[]).append(r)
    home_selected=[]
    for d,rows in sorted(home_by.items()):
        rows=sorted(rows,key=lambda x:(-x['p_home_novig'],x['B365H'],x['league_code'],x['HomeTeam'],x['AwayTeam']))[:3]
        for rank,r in enumerate(rows,1):home_selected.append({**r,'date_rank':rank})
    home_counts=Counter(r['date'] for r in home_selected)

    # Existing PASS +0.5 favorite, still max1/date. Used only as fallback when MULTI3 has zero legs.
    fav_by={}
    for r in valid:
        ph,pa=r['p_home_novig'],r['p_away_novig']
        if ph==pa:continue
        side='HOME' if ph>pa else 'AWAY'; pf=max(ph,pa)
        if pf<.60:continue
        price=r['B365H'] if side=='HOME' else r['B365A']
        entity=r['HomeTeam'] if side=='HOME' else r['AwayTeam']
        fav_by.setdefault(r['date'],[]).append({**r,'p_favorite_novig':pf,'selected_side':side,'selected_price':price,'selected_entity':entity})
    fav_selected=[]
    for d,rows in sorted(fav_by.items()):
        r=sorted(rows,key=lambda x:(-x['p_favorite_novig'],x['selected_price'],x['league_code'],x['HomeTeam'],x['AwayTeam'],x['selected_side']))[0]
        fav_selected.append(r)
    fav_map={r['date']:r for r in fav_selected}

    write_csv(OUT/'football_multi3_rows.csv',home_selected)
    write_csv(OUT/'football_favorite_plus0_5_rows.csv',fav_selected)

    t3_rows=[]
    with T3_LEDGER.open(newline='',encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            d=r['date'].strip()
            if START.isoformat()<=d<=END.isoformat():t3_rows.append(r)
    t3_counts=Counter(r['date'] for r in t3_rows)

    calendar=[]; hist=Counter(); d=START; missing=0; fallback_days=0
    while d<=END:
        ds=d.isoformat(); hm=int(home_counts.get(ds,0)); fallback=1 if hm==0 and ds in fav_map else 0
        if fallback:fallback_days+=1
        f=hm+fallback; t=int(t3_counts.get(ds,0)); total=f+t; hist[total]+=1; missing+=max(0,3-total)
        calendar.append({'date':ds,'football_multi3_home_legs':hm,'football_plus0_5_fallback_legs':fallback,'football_total_conservative_legs':f,'t3_distinct_event_legs':t,'total_candidate_legs':total,'core3_green':total>=3,'core4_green':total>=4,'core5_green':total>=5,'core6_green':total>=6})
        d+=timedelta(days=1)
    write_csv(OUT/'daily_multi3_fallback_plus_t3_matrix.csv',calendar)
    red=[r['date'] for r in calendar if r['total_candidate_legs']<3]
    summary={
      'window_start':START.isoformat(),'window_end':END.isoformat(),'calendar_days':len(calendar),
      'valid_football_events':len(valid),'football_multi3_selected_legs':len(home_selected),'football_multi3_candidate_dates':len(home_counts),'football_multi3_date_distribution':dict(sorted(Counter(home_counts.values()).items())),
      'favorite_plus0_5_candidate_dates':len(fav_map),'favorite_fallback_days_used':fallback_days,
      't3_rows':len(t3_rows),'t3_candidate_dates':len(t3_counts),
      'combined_histogram_0_to_6':{str(i):hist.get(i,0) for i in range(7)},
      'core3_days':sum(r['core3_green'] for r in calendar),'core3_rate':sum(r['core3_green'] for r in calendar)/len(calendar),
      'core4_days':sum(r['core4_green'] for r in calendar),'core5_days':sum(r['core5_green'] for r in calendar),'core6_days':sum(r['core6_green'] for r in calendar),
      'red_days_under3':len(red),'missing_leg_days_to_core3':missing,'longest_under3_streak':longest_red(calendar),'red_dates':red,
      'fallback_policy':'favorite +0.5 counts only when MULTI3 HOME count is zero; never stacks with MULTI3 in this conservative matrix',
      'outcomes_loaded_for_coverage':False,'source_audit':audit}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
