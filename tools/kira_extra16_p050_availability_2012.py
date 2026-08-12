from __future__ import annotations
import csv,io,json,math
from collections import Counter
from datetime import datetime
from pathlib import Path
import requests
OUT=Path('artifacts/kira_extra16_p050_availability_2012');OUT.mkdir(parents=True,exist_ok=True)
CODES=['ARG','AUT','BRA','CHN','DNK','FIN','IRL','JPN','MEX','NOR','POL','ROU','RUS','SWE','SWZ','USA'];YEAR=2012

def pdate(s):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(s).strip(),f).date()
        except:pass
    return None

def main():
    s=requests.Session();s.headers['User-Agent']='KIRA-X16-P050-AVAIL2012/1.0';out={};d50=Counter();d55=Counter();n50=n55=0
    for code in CODES:
        url=f'https://www.football-data.co.uk/new/{code}.csv'
        try:r=s.get(url,timeout=60);r.raise_for_status()
        except Exception as e:out[code]={'status':'ERR','reason':type(e).__name__};continue
        rows=list(csv.reader(io.StringIO(r.content.decode('utf-8-sig',errors='replace'))))
        if not rows:out[code]={'status':'EMPTY'};continue
        h=[x.strip() for x in rows[0]]
        if not all(c in h for c in ['Date','AvgCH','AvgCD','AvgCA']):out[code]={'status':'NO_SCHEMA'};continue
        idx={c:h.index(c) for c in ['Date','AvgCH','AvgCD','AvgCA']};mx=max(idx.values());rowsy=v50=v55=0
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']]);
            if d is None or d.year!=YEAR:continue
            rowsy+=1
            try:a,b,c=float(row[idx['AvgCH']]),float(row[idx['AvgCD']]),float(row[idx['AvgCA']])
            except:continue
            if not all(math.isfinite(x) and x>1 for x in (a,b,c)):continue
            qh,qd,qa=1/a,1/b,1/c;p=max(qh,qa)/(qh+qd+qa)
            if p>=.50:v50+=1;n50+=1;d50[d.isoformat()]+=1
            if p>=.55:v55+=1;n55+=1;d55[d.isoformat()]+=1
        out[code]={'status':'PASS','year_rows':rowsy,'p050_events':v50,'p055_events':v55}
    def pack(c):return {'candidate_dates':len(c),'selected_legs_max3':sum(min(3,n) for n in c.values()),'date_leg_distribution':dict(sorted(Counter(min(3,n) for n in c.values()).items())),'three_leg_dates':sum(n>=3 for n in c.values()),'first':min(c) if c else None,'last':max(c) if c else None}
    res={'year':YEAR,'sources':out,'p050_eligible_events':n50,'p055_eligible_events':n55,'p050':pack(d50),'p055':pack(d55),'outcomes_read':False}
    (OUT/'summary.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
if __name__=='__main__':main()
