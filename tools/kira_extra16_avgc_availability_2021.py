from __future__ import annotations
import csv,io,json,math
from collections import Counter
from datetime import datetime
from pathlib import Path
import requests
OUT=Path('artifacts/kira_extra16_avgc_availability_2021');OUT.mkdir(parents=True,exist_ok=True)
CODES=['ARG','AUT','BRA','CHN','DNK','FIN','IRL','JPN','MEX','NOR','POL','ROU','RUS','SWE','SWZ','USA']
YEAR=2021

def pdate(s):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(s).strip(),f).date()
        except:pass
    return None

def main():
    sess=requests.Session();sess.headers['User-Agent']='KIRA-EXTRA16-AVGCAUDIT/1.0'
    out={};all_dates=Counter();all_eligible=0
    for code in CODES:
        url=f'https://www.football-data.co.uk/new/{code}.csv'
        try:r=sess.get(url,timeout=45)
        except Exception as exc:
            out[code]={'url':url,'status':'REQUEST_ERROR','reason':type(exc).__name__};continue
        if r.status_code!=200:
            out[code]={'url':url,'status':'HTTP_ERROR','http':r.status_code};continue
        raw=r.content;rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))))
        if not rows:
            out[code]={'url':url,'status':'EMPTY'};continue
        h=[x.strip() for x in rows[0]];needed=['Date','AvgCH','AvgCD','AvgCA']
        if not all(c in h for c in needed):
            out[code]={'url':url,'status':'MISSING_COLUMNS','header':h};continue
        idx={c:h.index(c) for c in needed};mx=max(idx.values());year_rows=valid=eligible=0;dates=Counter()
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']]);
            if d is None or d.year!=YEAR:continue
            year_rows+=1
            try:a,b,c=float(row[idx['AvgCH']]),float(row[idx['AvgCD']]),float(row[idx['AvgCA']])
            except:continue
            if not all(math.isfinite(x) and x>1 for x in (a,b,c)):continue
            valid+=1; qh,qd,qa=1/a,1/b,1/c; p=max(qh,qa)/(qh+qd+qa)
            if p>=.60:
                eligible+=1;dates[d.isoformat()]+=1;all_dates[d.isoformat()]+=1;all_eligible+=1
        out[code]={'url':url,'status':'PASS','year_rows':year_rows,'valid_avgc_rows':valid,'favorite_p_ge_060_rows':eligible,'candidate_dates':len(dates),'first_candidate_date':min(dates) if dates else None,'last_candidate_date':max(dates) if dates else None}
    # Global max3 availability only; no result/score fields read.
    global_selected=sum(min(3,n) for n in all_dates.values())
    dist=Counter(min(3,n) for n in all_dates.values())
    summary={'year':YEAR,'codes':CODES,'sources':out,'eligible_events_all_sources':all_eligible,'global_candidate_dates':len(all_dates),'global_selected_legs_max3':global_selected,'date_leg_count_distribution_after_max3':dict(sorted(dist.items())),'outcomes_read':False}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
