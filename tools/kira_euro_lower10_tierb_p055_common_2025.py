from __future__ import annotations

import csv, hashlib, io, json, math
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
import requests

OUT=Path('artifacts/kira_euro_lower10_tierb_p055_common_2025');OUT.mkdir(parents=True,exist_ok=True)
START=date(2024,12,27);END=date(2025,12,17)
LEAGUES=['E1','E2','E3','SP2','D2','I2','F2','SC1','SC2','SC3'];SEASONS=['2425','2526']
REQ=['Date','HomeTeam','AwayTeam','AvgCH','AvgCD','AvgCA'];P_MIN=.55;MAX_DATE=3

def pdate(v):
    s=str(v or '').strip()
    for fmt in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(s,fmt).date()
        except:pass
    return None

def decode(raw):
    for enc in ('utf-8-sig','latin-1'):
        try:return enc,list(csv.reader(io.StringIO(raw.decode(enc),newline='')))
        except:pass
    raise RuntimeError('CSV_DECODE_FAILED')

def write_csv(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    s=requests.Session();s.headers['User-Agent']='KIRA-EURO-LOWER10-P055-COMMON25/1.0 outcome-blind'
    eligible=[];audit=[];seen=set()
    for season in SEASONS:
      for league in LEAGUES:
        url=f'https://www.football-data.co.uk/mmz4281/{season}/{league}.csv'
        try:r=s.get(url,timeout=45);r.raise_for_status();raw=r.content;enc,rows=decode(raw)
        except Exception as exc:
            audit.append({'season':season,'league':league,'status':'SOURCE_UNUSABLE','reason':type(exc).__name__});continue
        sha=hashlib.sha256(raw).hexdigest();header=None;hi=None
        for i,row in enumerate(rows):
            h=[str(x).strip() for x in row]
            if all(c in h for c in REQ):header=h;hi=i;break
        if header is None:
            audit.append({'season':season,'league':league,'status':'SOURCE_UNUSABLE','sha256':sha,'reason':'MISSING_PREMATCH_COLUMNS'});continue
        idx={c:header.index(c) for c in REQ};mx=max(idx.values());serial=[];valid=0;n=0
        for row in rows[hi+1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']])
            if d is None or d<START or d>END:continue
            serial.append(','.join(row));home=row[idx['HomeTeam']].strip();away=row[idx['AwayTeam']].strip()
            try:h=float(row[idx['AvgCH']]);dr=float(row[idx['AvgCD']]);a=float(row[idx['AvgCA']])
            except:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h,dr,a)):continue
            valid+=1;qh,qd,qa=1/h,1/dr,1/a;den=qh+qd+qa;ph,pa=qh/den,qa/den
            if ph==pa:continue
            side='HOME' if ph>pa else 'AWAY';prob=max(ph,pa)
            if prob<P_MIN:continue
            key=(d.isoformat(),league,home,away)
            if key in seen:continue
            seen.add(key);price=h if side=='HOME' else a;ent=home if side=='HOME' else away;eid='EL10C-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            eligible.append({'date':d.isoformat(),'season':season,'league':league,'Home':home,'Away':away,'selected_side':side,'selected_entity':ent,'selected_price':price,'p_favorite_novig':prob,'event_id':eid});n+=1
        audit.append({'season':season,'league':league,'status':'PASS','sha256':sha,'encoding':enc,'target_window_rows':len(serial),'target_window_rows_sha256':hashlib.sha256('\n'.join(serial).encode()).hexdigest(),'valid_prematch_window_rows':valid,'eligible_pre_cap':n,'outcome_columns_requested':False})
    if len(audit)!=len(SEASONS)*len(LEAGUES) or any(x.get('status')!='PASS' for x in audit):
        res={'decision':'SOURCE_GATE_FAIL','source_audit':audit};(OUT/'summary.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2));return
    by=defaultdict(list)
    for x in eligible:by[x['date']].append(x)
    selected=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(-x['p_favorite_novig'],x['selected_price'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:MAX_DATE]
        for rank,x in enumerate(rr,1):selected.append({**x,'date_rank':rank})
    write_csv(OUT/'lower10_p055_rows_common_2025.csv',selected)
    cnt=Counter(x['date'] for x in selected)
    res={'hypothesis_id':'FOOTBALL_EURO_LOWER10_TIERB_P055_TRANSPORT_V2_GATE90','mode':'OUTCOME_BLIND_COMMON_WINDOW_RECONSTRUCTION','window':[START.isoformat(),END.isoformat()],'calendar_days':(END-START).days+1,'seasons':SEASONS,'leagues':LEAGUES,'p_min':P_MIN,'max_per_date':MAX_DATE,'eligible_pre_cap':len(eligible),'selected_legs':len(selected),'candidate_dates':len(cnt),'date_leg_count_distribution':dict(sorted(Counter(cnt.values()).items())),'three_leg_dates':sum(v>=3 for v in cnt.values()),'outcomes_loaded':False,'outcome_columns_requested':False,'source_audit':audit}
    (OUT/'summary.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
if __name__=='__main__':main()
