from __future__ import annotations
import csv,io,json,hashlib,math
from collections import Counter
from datetime import datetime
from pathlib import Path
import requests
OUT=Path('artifacts/kira_summer_favorite_plus1_5_multi3_avgc_calendar_2025');OUT.mkdir(parents=True,exist_ok=True)
SOURCES={'BRA':'https://www.football-data.co.uk/new/BRA.csv','USA':'https://www.football-data.co.uk/new/USA.csv'}
REQ=['Country','League','Season','Date','Home','Away','AvgCH','AvgCD','AvgCA']
YEAR=2025;TH=.60;MAX_PER_DATE=3

def parse_date(s):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(s).strip(),f).date()
        except:pass
    return None
def write_csv(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
    sess=requests.Session();sess.headers['User-Agent']='KIRA-SUMMER-AVGC15-CALENDAR/1.0'
    audit=[];eligible=[];seen=set()
    for code,url in SOURCES.items():
        r=sess.get(url,timeout=60);r.raise_for_status();raw=r.content
        rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))));h=[x.strip() for x in rows[0]];idx={c:h.index(c) for c in REQ};mx=max(idx.values());year_rows=[]
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=parse_date(row[idx['Date']]);
            if d is None or d.year!=YEAR:continue
            year_rows.append(','.join(row))
            home=row[idx['Home']].strip();away=row[idx['Away']].strip();league=row[idx['League']].strip()
            try:h1=float(row[idx['AvgCH']]);dr=float(row[idx['AvgCD']]);a1=float(row[idx['AvgCA']])
            except:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h1,dr,a1)):continue
            qh,qd,qa=1/h1,1/dr,1/a1;den=qh+qd+qa;ph,pa=qh/den,qa/den
            if ph==pa:continue
            side='HOME' if ph>pa else 'AWAY';pf=max(ph,pa);price=h1 if side=='HOME' else a1;entity=home if side=='HOME' else away
            if pf<TH:continue
            key=(d.isoformat(),code,league,home,away)
            if key in seen:continue
            seen.add(key);eid='FS25-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            eligible.append({'date':d.isoformat(),'source':code,'league':league,'Home':home,'Away':away,'selected_side':side,'selected_entity':entity,'selected_price':price,'p_favorite_novig':pf,'event_id':eid})
        audit.append({'source':code,'file_sha256':hashlib.sha256(raw).hexdigest(),'target_year_rows_sha256':hashlib.sha256('\n'.join(year_rows).encode()).hexdigest(),'target_year_rows':len(year_rows)})
    by={}
    for x in eligible:by.setdefault(x['date'],[]).append(x)
    selected=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(-x['p_favorite_novig'],x['selected_price'],x['source'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:MAX_PER_DATE]
        for rank,x in enumerate(rr,1):selected.append({**x,'date_rank':rank})
    write_csv(OUT/'summer_multi3_rows_2025.csv',selected)
    cnt=Counter(x['date'] for x in selected);summary={'hypothesis_id':'FOOTBALL_SUMMER_FAVORITE_PLUS1_5_MULTI3_V2_AVGC','year':YEAR,'eligible_pre_cap':len(eligible),'selected_legs':len(selected),'candidate_dates':len(cnt),'date_leg_count_distribution':dict(sorted(Counter(cnt.values()).items())),'source_audit':audit,'threshold':TH,'max_per_date':MAX_PER_DATE,'outcomes_loaded':False}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
