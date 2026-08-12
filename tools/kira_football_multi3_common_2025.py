from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime, date
from pathlib import Path

import requests

OUT=Path('artifacts/kira_football_multi3_common_2025')
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

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    s=requests.Session();s.headers['User-Agent']='KIRA-MULTI3-common-calendar/1.0'
    audit=[]; events=[]; seen=set()
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
            vals={c:row[j] for c,j in idx.items()}
            d=parse_date(vals['Date'])
            if d is None or d<START or d>END:continue
            home=str(vals['HomeTeam']).strip();away=str(vals['AwayTeam']).strip()
            try:h=float(vals['B365H']);dr=float(vals['B365D']);a=float(vals['B365A'])
            except Exception:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h,dr,a)):continue
            key=(d.isoformat(),lg,home,away)
            if key in seen:continue
            seen.add(key)
            qh,qd,qa=1/h,1/dr,1/a; ph=qh/(qh+qd+qa)
            if ph<.75:continue
            eid='FMOD-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            events.append({'date':d.isoformat(),'season':season,'league_code':lg,'HomeTeam':home,'AwayTeam':away,'B365H':h,'B365D':dr,'B365A':a,'p_home_novig':ph,'event_id':eid});accepted+=1
        audit.append({'season':season,'league':lg,'status':'PASS','sha256':sha,'bytes':len(raw),'encoding':enc,'eligible_in_window':accepted})
    by={}
    for r in events:by.setdefault(r['date'],[]).append(r)
    selected=[]
    for d,rows in sorted(by.items()):
        rows=sorted(rows,key=lambda x:(-x['p_home_novig'],x['B365H'],x['league_code'],x['HomeTeam'],x['AwayTeam']))[:3]
        for rank,r in enumerate(rows,1):selected.append({**r,'date_rank':rank})
    dist=Counter()
    for d in by:
        dist[min(3,len(by[d]))]+=1
    write_csv(OUT/'football_multi3_rows.csv',selected)
    summary={'window_start':START.isoformat(),'window_end':END.isoformat(),'calendar_days':(END-START).days+1,'eligible_events_pre_cap':len(events),'selected_legs':len(selected),'candidate_dates':len({r['date'] for r in selected}),'date_leg_count_distribution':dict(sorted(dist.items())),'max3_selector':True,'threshold':.75,'outcomes_loaded':False,'source_audit':audit}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
