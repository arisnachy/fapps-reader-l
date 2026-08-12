from __future__ import annotations
import csv,io,json,math
from collections import Counter
from datetime import datetime
from pathlib import Path
import requests
OUT=Path('artifacts/kira_global_football_tierb_availability_2013');OUT.mkdir(parents=True,exist_ok=True)
YEAR=2013
EURO_SEASONS=['1213','1314'];EURO_LEAGUES=['E0','SP1','D1','I1','F1','N1','P1','SC0','B1']
EXTRA=['ARG','AUT','BRA','CHN','DNK','FIN','IRL','JPN','MEX','NOR','POL','ROU','RUS','SWE','SWZ','USA']

def pdate(s):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(s).strip(),f).date()
        except:pass
    return None
def decode(raw):
    for e in ('utf-8-sig','latin-1'):
        try:return list(csv.reader(io.StringIO(raw.decode(e),newline='')))
        except:pass
    return []
def main():
    s=requests.Session();s.headers['User-Agent']='KIRA-GLOBAL-TIERB-AVAIL2013/1.0';events=[];audit=[]
    # Europe HOME p>=.75
    for season in EURO_SEASONS:
      for lg in EURO_LEAGUES:
        url=f'https://www.football-data.co.uk/mmz4281/{season}/{lg}.csv'
        try:r=s.get(url,timeout=45);r.raise_for_status()
        except Exception as e:audit.append({'route':'EUROPE','source':f'{season}:{lg}','status':'ERR','reason':type(e).__name__});continue
        rows=decode(r.content);header=None;hi=None
        for i,row in enumerate(rows):
            h=[str(x).strip() for x in row]
            if all(c in h for c in ['Date','HomeTeam','AwayTeam','B365H','B365D','B365A']):header=h;hi=i;break
        if header is None:audit.append({'route':'EUROPE','source':f'{season}:{lg}','status':'NO_SCHEMA'});continue
        idx={c:header.index(c) for c in ['Date','HomeTeam','AwayTeam','B365H','B365D','B365A']};mx=max(idx.values());n=0
        for row in rows[hi+1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']]);
            if d is None or d.year!=YEAR:continue
            try:h=float(row[idx['B365H']]);dr=float(row[idx['B365D']]);a=float(row[idx['B365A']])
            except:continue
            if not all(math.isfinite(x) and x>1 for x in (h,dr,a)):continue
            qh,qd,qa=1/h,1/dr,1/a;ph=qh/(qh+qd+qa)
            if ph>=.75:events.append((d.isoformat(),ph,'EUROPE',lg));n+=1
        audit.append({'route':'EUROPE','source':f'{season}:{lg}','status':'PASS','eligible':n})
    # Extra16 p>=.55 AvgC
    for code in EXTRA:
        url=f'https://www.football-data.co.uk/new/{code}.csv'
        try:r=s.get(url,timeout=45);r.raise_for_status()
        except Exception as e:audit.append({'route':'EXTRA16','source':code,'status':'ERR','reason':type(e).__name__});continue
        rows=decode(r.content)
        if not rows:audit.append({'route':'EXTRA16','source':code,'status':'EMPTY'});continue
        h=[str(x).strip() for x in rows[0]]
        if not all(c in h for c in ['Date','AvgCH','AvgCD','AvgCA']):audit.append({'route':'EXTRA16','source':code,'status':'NO_SCHEMA'});continue
        idx={c:h.index(c) for c in ['Date','AvgCH','AvgCD','AvgCA']};mx=max(idx.values());n=0
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']]);
            if d is None or d.year!=YEAR:continue
            try:a,b,c=float(row[idx['AvgCH']]),float(row[idx['AvgCD']]),float(row[idx['AvgCA']])
            except:continue
            if not all(math.isfinite(x) and x>1 for x in (a,b,c)):continue
            qh,qd,qa=1/a,1/b,1/c;pf=max(qh,qa)/(qh+qd+qa)
            if pf>=.55:events.append((d.isoformat(),pf,'EXTRA16',code));n+=1
        audit.append({'route':'EXTRA16','source':code,'status':'PASS','eligible':n})
    by={}
    for d,p,r,sr in events:by.setdefault(d,[]).append((p,r,sr))
    selected={d:sorted(v,key=lambda x:(-x[0],x[1],x[2]))[:3] for d,v in by.items()}
    cnt=Counter(len(v) for v in selected.values())
    all_dates=[f'{YEAR}-{m:02d}-{d:02d}' for m in range(1,13) for d in range(1,32) if __import__('datetime').date(YEAR,m,1).replace(day=1) and (lambda: True)()]
    # Avoid invalid-day machinery in summary; calendar denominator fixed by date range.
    res={'year':YEAR,'eligible_events':len(events),'candidate_dates':len(selected),'selected_legs_max3':sum(len(v) for v in selected.values()),'date_leg_distribution':dict(sorted(cnt.items())),'three_leg_dates':sum(len(v)==3 for v in selected.values()),'first':min(selected) if selected else None,'last':max(selected) if selected else None,'europe_eligible':sum(1 for x in events if x[2]=='EUROPE'),'extra16_eligible':sum(1 for x in events if x[2]=='EXTRA16'),'audit':audit,'outcomes_read':False}
    (OUT/'summary.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
if __name__=='__main__':main()
