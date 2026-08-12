from __future__ import annotations
import csv,io,json,math
from collections import Counter
from datetime import datetime
from pathlib import Path
import requests
OUT=Path('artifacts/kira_extra16_p055_availability_2019');OUT.mkdir(parents=True,exist_ok=True)
CODES=['ARG','AUT','BRA','CHN','DNK','FIN','IRL','JPN','MEX','NOR','POL','ROU','RUS','SWE','SWZ','USA'];YEAR=2019

def pdate(s):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(s).strip(),f).date()
        except:pass
    return None

def main():
    s=requests.Session();s.headers['User-Agent']='KIRA-X16-P055-AVAIL/1.0';out={};d55=Counter();d60=Counter();n55=n60=0
    for code in CODES:
        r=s.get(f'https://www.football-data.co.uk/new/{code}.csv',timeout=60);r.raise_for_status();rows=list(csv.reader(io.StringIO(r.content.decode('utf-8-sig',errors='replace'))));h=[x.strip() for x in rows[0]]
        req=['Date','AvgCH','AvgCD','AvgCA'];idx={c:h.index(c) for c in req};mx=max(idx.values());c55=c60=rowsy=0
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']]);
            if d is None or d.year!=YEAR:continue
            rowsy+=1
            try:a,b,c=float(row[idx['AvgCH']]),float(row[idx['AvgCD']]),float(row[idx['AvgCA']])
            except:continue
            if not all(math.isfinite(x) and x>1 for x in (a,b,c)):continue
            qh,qd,qa=1/a,1/b,1/c;p=max(qh,qa)/(qh+qd+qa)
            if p>=.55:c55+=1;n55+=1;d55[d.isoformat()]+=1
            if p>=.60:c60+=1;n60+=1;d60[d.isoformat()]+=1
        out[code]={'year_rows':rowsy,'p055_events':c55,'p060_events':c60}
    def pack(d):
        return {'candidate_dates':len(d),'selected_legs_max3':sum(min(3,n) for n in d.values()),'date_leg_distribution':dict(sorted(Counter(min(3,n) for n in d.values()).items())),'three_leg_dates':sum(n>=3 for n in d.values()),'first':min(d) if d else None,'last':max(d) if d else None}
    res={'year':YEAR,'sources':out,'p055_eligible_events':n55,'p060_eligible_events':n60,'p055':pack(d55),'p060':pack(d60),'outcomes_read':False}
    (OUT/'summary.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
if __name__=='__main__':main()
