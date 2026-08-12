from __future__ import annotations
import csv,hashlib,io,json,math
from collections import Counter,defaultdict
from datetime import date,datetime
from pathlib import Path
import requests
OUT=Path('artifacts/kira_euro19_opponent_tt_u35_margin_p50_55_common_2025');OUT.mkdir(parents=True,exist_ok=True)
START=date(2024,12,27);END=date(2025,12,17);SEASONS=['2425','2526'];LEAGUES=['E0','E1','E2','E3','SP1','SP2','D1','D2','I1','I2','F1','F2','N1','P1','SC0','SC1','SC2','SC3','B1'];REQ=['Date','HomeTeam','AwayTeam','AvgCH','AvgCD','AvgCA'];LOW=.50;HIGH=.55;MAXD=3

def pdate(v):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(v).strip(),f).date()
        except:pass
    return None
def decode(raw):
    for enc in ('utf-8-sig','latin-1'):
        try:return enc,list(csv.reader(io.StringIO(raw.decode(enc),newline='')))
        except:pass
    raise RuntimeError('DECODE')
def write(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fs=[]
    for r in rows:
        for k in r:
            if k not in fs:fs.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:w=csv.DictWriter(fh,fieldnames=fs);w.writeheader();w.writerows(rows)
def main():
    s=requests.Session();s.headers['User-Agent']='KIRA-EURO19-U35-MARGIN-COMMON25/1.0 outcome-blind';eligible=[];audit=[];seen=set()
    for season in SEASONS:
      for lg in LEAGUES:
        url=f'https://www.football-data.co.uk/mmz4281/{season}/{lg}.csv'
        try:r=s.get(url,timeout=45);r.raise_for_status();raw=r.content;enc,rows=decode(raw)
        except Exception as exc:audit.append({'season':season,'league':lg,'status':'SOURCE_UNUSABLE','reason':type(exc).__name__});continue
        sha=hashlib.sha256(raw).hexdigest();header=None;hi=None
        for i,row in enumerate(rows):
            h=[str(x).strip() for x in row]
            if all(c in h for c in REQ):header=h;hi=i;break
        if header is None:audit.append({'season':season,'league':lg,'status':'SOURCE_UNUSABLE','sha256':sha,'reason':'MISSING_PREMATCH_COLUMNS'});continue
        ix={c:header.index(c) for c in REQ};mx=max(ix.values());serial=[];n=0
        for row in rows[hi+1:]:
            if len(row)<=mx:continue
            d=pdate(row[ix['Date']])
            if d is None or d<START or d>END:continue
            serial.append(','.join(row));home=row[ix['HomeTeam']].strip();away=row[ix['AwayTeam']].strip()
            try:h=float(row[ix['AvgCH']]);dr=float(row[ix['AvgCD']]);a=float(row[ix['AvgCA']])
            except:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h,dr,a)):continue
            qh,qd,qa=1/h,1/dr,1/a;den=qh+qd+qa;ph,pa=qh/den,qa/den
            if ph==pa:continue
            side='HOME' if ph>pa else 'AWAY';prob=max(ph,pa)
            if not (LOW<=prob<HIGH):continue
            key=(d.isoformat(),lg,home,away)
            if key in seen:continue
            seen.add(key);sel=home if side=='HOME' else away;opp=away if side=='HOME' else home;price=h if side=='HOME' else a;eid='E19MC-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            eligible.append({'date':d.isoformat(),'season':season,'league':lg,'Home':home,'Away':away,'selected_side':side,'selected_entity':sel,'opponent_entity':opp,'selected_price':price,'p_selected_novig':prob,'event_id':eid});n+=1
        audit.append({'season':season,'league':lg,'status':'PASS','sha256':sha,'encoding':enc,'target_window_rows':len(serial),'target_window_rows_sha256':hashlib.sha256('\n'.join(serial).encode()).hexdigest(),'eligible_band_pre_cap':n,'outcome_columns_requested':False})
    if len(audit)!=len(SEASONS)*len(LEAGUES) or any(x.get('status')!='PASS' for x in audit):
        r={'decision':'SOURCE_GATE_FAIL','source_audit':audit};(OUT/'summary.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2));return
    by=defaultdict(list)
    for x in eligible:by[x['date']].append(x)
    sel=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(-x['p_selected_novig'],x['selected_price'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:MAXD]
        for rank,x in enumerate(rr,1):sel.append({**x,'date_rank':rank})
    write(OUT/'euro19_u35_margin_p50_55_rows_common_2025.csv',sel);cnt=Counter(x['date'] for x in sel)
    r={'hypothesis_id':'FOOTBALL_EURO19_OPPONENT_TT_U35_MARGIN_P50_55_V1','mode':'OUTCOME_BLIND_COMMON_WINDOW_RECONSTRUCTION','window':[START.isoformat(),END.isoformat()],'frozen_band':[LOW,HIGH],'eligible_band_pre_cap':len(eligible),'selected_legs':len(sel),'candidate_dates':len(cnt),'date_leg_count_distribution':dict(sorted(Counter(cnt.values()).items())),'outcomes_loaded':False,'outcome_columns_requested':False,'source_audit':audit};(OUT/'summary.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
if __name__=='__main__':main()
