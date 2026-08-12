from __future__ import annotations
import csv,io,json,math
from collections import Counter
from datetime import datetime
from pathlib import Path
import requests
OUT=Path('artifacts/kira_extra16_p055_pinnacle_availability_2020');OUT.mkdir(parents=True,exist_ok=True)
CODES=['ARG','AUT','BRA','CHN','DNK','FIN','IRL','JPN','MEX','NOR','POL','ROU','RUS','SWE','SWZ','USA'];YEAR=2020

def pdate(s):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(s).strip(),f).date()
        except:pass
    return None

def main():
    s=requests.Session();s.headers['User-Agent']='KIRA-X16-PSC-P055-AVAIL2020/1.0';out={};dates=Counter();eligible=0
    for code in CODES:
        url=f'https://www.football-data.co.uk/new/{code}.csv'
        try:r=s.get(url,timeout=60);r.raise_for_status()
        except Exception as e:out[code]={'status':'ERR','reason':type(e).__name__};continue
        rows=list(csv.reader(io.StringIO(r.content.decode('utf-8-sig',errors='replace'))));h=[x.strip() for x in rows[0]] if rows else []
        req=['Date','PSCH','PSCD','PSCA']
        if not all(c in h for c in req):out[code]={'status':'NO_SCHEMA','has':{c:c in h for c in req}};continue
        idx={c:h.index(c) for c in req};mx=max(idx.values());yr=valid=n=0
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']]);
            if d is None or d.year!=YEAR:continue
            yr+=1
            try:a,b,c=float(row[idx['PSCH']]),float(row[idx['PSCD']]),float(row[idx['PSCA']])
            except:continue
            if not all(math.isfinite(x) and x>1 for x in (a,b,c)):continue
            valid+=1;qh,qd,qa=1/a,1/b,1/c;p=max(qh,qa)/(qh+qd+qa)
            if p>=.55:n+=1;eligible+=1;dates[d.isoformat()]+=1
        out[code]={'status':'PASS','year_rows':yr,'valid_pinnacle_rows':valid,'p055_events':n}
    res={'year':YEAR,'sources':out,'eligible_events':eligible,'candidate_dates':len(dates),'selected_legs_max3':sum(min(3,n) for n in dates.values()),'date_leg_distribution':dict(sorted(Counter(min(3,n) for n in dates.values()).items())),'three_leg_dates':sum(n>=3 for n in dates.values()),'first':min(dates) if dates else None,'last':max(dates) if dates else None,'outcomes_read':False}
    (OUT/'summary.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
if __name__=='__main__':main()
