from __future__ import annotations
import csv,io,json,hashlib,math
from collections import Counter
from datetime import datetime,date
from pathlib import Path
import requests
OUT=Path('artifacts/kira_extra16_favorite_plus1_5_multi3_calendar_2025');OUT.mkdir(parents=True,exist_ok=True)
CODES=['ARG','AUT','BRA','CHN','DNK','FIN','IRL','JPN','MEX','NOR','POL','ROU','RUS','SWE','SWZ','USA']
REQ=['Date','Home','Away','League','AvgCH','AvgCD','AvgCA']
START=date(2024,12,27);END=date(2025,12,17);TH=.60

def pdate(s):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(s).strip(),f).date()
        except:pass
    return None
def write(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
    s=requests.Session();s.headers['User-Agent']='KIRA-EXTRA16-CALENDAR25/1.0';audit=[];eligible=[];seen=set()
    for code in CODES:
        url=f'https://www.football-data.co.uk/new/{code}.csv';r=s.get(url,timeout=60);r.raise_for_status();raw=r.content
        rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))));h=[x.strip() for x in rows[0]]
        miss=[c for c in REQ if c not in h]
        if miss:audit.append({'source':code,'status':'MISSING_COLUMNS','missing':miss});continue
        idx={c:h.index(c) for c in REQ};mx=max(idx.values());serial=[];n=0
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']]);
            if d is None or d<START or d>END:continue
            serial.append(','.join(row));home=row[idx['Home']].strip();away=row[idx['Away']].strip();lg=row[idx['League']].strip()
            try:h1=float(row[idx['AvgCH']]);dr=float(row[idx['AvgCD']]);a1=float(row[idx['AvgCA']])
            except:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h1,dr,a1)):continue
            qh,qd,qa=1/h1,1/dr,1/a1;den=qh+qd+qa;ph,pa=qh/den,qa/den
            if ph==pa:continue
            side='HOME' if ph>pa else 'AWAY';prob=max(ph,pa)
            if prob<TH:continue
            price=h1 if side=='HOME' else a1;ent=home if side=='HOME' else away;key=(d.isoformat(),code,lg,home,away)
            if key in seen:continue
            seen.add(key);eid='X25-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            eligible.append({'date':d.isoformat(),'source':code,'league':lg,'Home':home,'Away':away,'selected_side':side,'selected_entity':ent,'selected_price':price,'p_favorite_novig':prob,'event_id':eid});n+=1
        audit.append({'source':code,'status':'PASS','file_sha256':hashlib.sha256(raw).hexdigest(),'target_window_rows_sha256':hashlib.sha256('\n'.join(serial).encode()).hexdigest(),'target_window_rows':len(serial),'eligible_pre_cap':n})
    if any(x.get('status')!='PASS' for x in audit):
        res={'decision':'SOURCE_GATE_FAIL','source_audit':audit};(OUT/'summary.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2));return
    by={}
    for x in eligible:by.setdefault(x['date'],[]).append(x)
    selected=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(-x['p_favorite_novig'],x['selected_price'],x['source'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:3]
        for rank,x in enumerate(rr,1):selected.append({**x,'date_rank':rank})
    write(OUT/'extra16_multi3_rows_common_2025.csv',selected)
    cnt=Counter(x['date'] for x in selected);summary={'hypothesis_id':'FOOTBALL_EXTRA16_FAVORITE_PLUS1_5_MULTI3_V1','window':[START.isoformat(),END.isoformat()],'calendar_days':(END-START).days+1,'eligible_pre_cap':len(eligible),'selected_legs':len(selected),'candidate_dates':len(cnt),'date_leg_count_distribution':dict(sorted(Counter(cnt.values()).items())),'source_selected_counts':dict(sorted(Counter(x['source'] for x in selected).items())),'source_audit':audit,'outcomes_loaded':False}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
