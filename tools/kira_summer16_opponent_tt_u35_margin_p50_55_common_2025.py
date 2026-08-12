from __future__ import annotations
import csv,io,json,hashlib,math
from collections import Counter,defaultdict
from datetime import date,datetime
from pathlib import Path
import requests
OUT=Path('artifacts/kira_summer16_opponent_tt_u35_margin_p50_55_common_2025');OUT.mkdir(parents=True,exist_ok=True)
CODES=['ARG','AUT','BRA','CHN','DNK','FIN','IRL','JPN','MEX','NOR','POL','ROU','RUS','SWE','SWZ','USA']
REQ=['Date','Home','Away','League','AvgCH','AvgCD','AvgCA'];START=date(2024,12,27);END=date(2025,12,17);LOW=.50;HIGH=.55;MAXD=3

def pdate(v):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(v).strip(),f).date()
        except:pass
    return None
def write(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fs=[]
    for r in rows:
        for k in r:
            if k not in fs:fs.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:w=csv.DictWriter(fh,fieldnames=fs);w.writeheader();w.writerows(rows)
def main():
    s=requests.Session();s.headers['User-Agent']='KIRA-SUMMER16-U35-MARGIN-COMMON25/1.0 outcome-blind';eligible=[];audit=[];seen=set()
    for code in CODES:
        url=f'https://www.football-data.co.uk/new/{code}.csv'
        try:r=s.get(url,timeout=60);r.raise_for_status();raw=r.content;rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))))
        except Exception as exc:audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':type(exc).__name__});continue
        if not rows:audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':'EMPTY'});continue
        h=[x.strip() for x in rows[0]];miss=[c for c in REQ if c not in h]
        if miss:audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':'MISSING_COLUMNS','missing':miss});continue
        ix={c:h.index(c) for c in REQ};mx=max(ix.values());serial=[];n=0
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=pdate(row[ix['Date']])
            if d is None or d<START or d>END:continue
            serial.append(','.join(row));home=row[ix['Home']].strip();away=row[ix['Away']].strip();lg=row[ix['League']].strip()
            try:h1=float(row[ix['AvgCH']]);dr=float(row[ix['AvgCD']]);a1=float(row[ix['AvgCA']])
            except:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h1,dr,a1)):continue
            qh,qd,qa=1/h1,1/dr,1/a1;den=qh+qd+qa;ph,pa=qh/den,qa/den
            if ph==pa:continue
            side='HOME' if ph>pa else 'AWAY';prob=max(ph,pa)
            if not (LOW<=prob<HIGH):continue
            key=(d.isoformat(),code,lg,home,away)
            if key in seen:continue
            seen.add(key);sel=home if side=='HOME' else away;opp=away if side=='HOME' else home;price=h1 if side=='HOME' else a1;eid='S16MC-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            eligible.append({'date':d.isoformat(),'source':code,'league':lg,'Home':home,'Away':away,'selected_side':side,'selected_entity':sel,'opponent_entity':opp,'selected_price':price,'p_selected_novig':prob,'event_id':eid});n+=1
        audit.append({'source':code,'status':'PASS','file_sha256':hashlib.sha256(raw).hexdigest(),'target_window_rows_sha256':hashlib.sha256('\n'.join(serial).encode()).hexdigest(),'target_window_rows':len(serial),'eligible_band_pre_cap':n,'outcome_columns_requested':False})
    if len(audit)!=len(CODES) or any(x.get('status')!='PASS' for x in audit):
        r={'decision':'SOURCE_GATE_FAIL','source_audit':audit};(OUT/'summary.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2));return
    by=defaultdict(list)
    for x in eligible:by[x['date']].append(x)
    sel=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(-x['p_selected_novig'],x['selected_price'],x['source'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:MAXD]
        for rank,x in enumerate(rr,1):sel.append({**x,'date_rank':rank})
    write(OUT/'summer16_u35_margin_p50_55_rows_common_2025.csv',sel);cnt=Counter(x['date'] for x in sel)
    r={'hypothesis_id':'FOOTBALL_SUMMER16_OPPONENT_TT_U35_MARGIN_P50_55_V1','mode':'OUTCOME_BLIND_COMMON_WINDOW_RECONSTRUCTION','window':[START.isoformat(),END.isoformat()],'frozen_band':[LOW,HIGH],'eligible_band_pre_cap':len(eligible),'selected_legs':len(sel),'candidate_dates':len(cnt),'date_leg_count_distribution':dict(sorted(Counter(cnt.values()).items())),'outcomes_loaded':False,'outcome_columns_requested':False,'source_audit':audit};(OUT/'summary.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
if __name__=='__main__':main()
