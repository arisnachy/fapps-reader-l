from __future__ import annotations

import hashlib, io, json, math, re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
import requests

OUT=Path('artifacts/kira_tennis_r4_10_plus7_5_common_2025');OUT.mkdir(parents=True,exist_ok=True)
START=date(2024,12,27);END=date(2025,12,17);YEARS=[2024,2025]
USECOLS=['Date','Best of','Winner','Loser','WRank','LRank','Tournament','Round']
LOW=4;HIGH=10;OPP_MIN=30;MAX_DATE=3

def clean(v):return re.sub(r'\s+',' ',str(v or '')).strip()
def rank(v):
    try:
        x=float(v)
        if not math.isfinite(x) or x<=0:return None
        return int(x)
    except:return None
def dstr(v):
    try:
        x=pd.to_datetime(v,errors='coerce')
        if pd.isna(x):return ''
        return x.date().isoformat()
    except:return ''
def download(year):
    s=requests.Session();s.headers['User-Agent']='KIRA-TENNIS-R4-10-P75-COMMON25/1.0 outcome-blind'
    errors=[]
    for scheme in ('https','http'):
        url=f'{scheme}://www.tennis-data.co.uk/{year}/{year}.xlsx'
        try:
            r=s.get(url,timeout=90);r.raise_for_status();raw=r.content
            df=pd.read_excel(io.BytesIO(raw),sheet_name=str(year),usecols=USECOLS,engine='openpyxl')
            return df,{'year':year,'status':'PASS','scheme':scheme,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'url_path':f'/{year}/{year}.xlsx','rows_loaded':len(df),'loaded_columns':[str(x) for x in df.columns],'score_result_columns_loaded':False}
        except Exception as exc:errors.append(f'{scheme}:{type(exc).__name__}')
    raise RuntimeError('DOWNLOAD_FAILED '+','.join(errors))
def main():
    all_rows=[];audits=[]
    for year in YEARS:
        try:df,audit=download(year)
        except Exception as exc:
            result={'decision':'SOURCE_GATE_FAIL','year':year,'reason':f'{type(exc).__name__}:{exc}','source_audit':audits};(OUT/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));return
        audits.append(audit)
        for idx,row in df.iterrows():
            try:best=int(float(row['Best of']))
            except:continue
            if best!=3:continue
            wr,lr=rank(row['WRank']),rank(row['LRank'])
            if wr is None or lr is None:continue
            winner,loser=clean(row['Winner']),clean(row['Loser'])
            if not winner or not loser:continue
            ws=LOW<=wr<=HIGH and lr>=OPP_MIN;ls=LOW<=lr<=HIGH and wr>=OPP_MIN
            if ws==ls:continue
            ds=dstr(row['Date'])
            if not ds:continue
            dd=pd.Timestamp(ds).date()
            if dd<START or dd>END:continue
            selected=winner if ws else loser;opp=loser if ws else winner;sr=wr if ws else lr;orr=lr if ws else wr;tour=clean(row['Tournament']);rnd=clean(row['Round'])
            identity=f'{ds}|{winner}|{loser}|{tour}|{rnd}|{year}|{idx}'
            all_rows.append({'date':ds,'source_year':year,'source_row':int(idx),'winner':winner,'loser':loser,'selected_player':selected,'opponent':opp,'selected_rank':sr,'opponent_rank':orr,'tournament':tour,'round':rnd,'match_id':'TR475C-'+hashlib.sha256(identity.encode()).hexdigest()[:20]})
    by=defaultdict(list)
    for x in all_rows:by[x['date']].append(x)
    selected=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(x['selected_rank'],-x['opponent_rank'],x['selected_player'],x['opponent'],x['tournament'],x['round'],x['source_year'],x['source_row']))[:MAX_DATE]
        for rank_i,x in enumerate(rr,1):selected.append({**x,'date_rank':rank_i})
    pd.DataFrame(selected).to_csv(OUT/'tennis_r4_10_plus7_5_rows_common_2025.csv',index=False)
    counts=Counter(x['date'] for x in selected)
    result={'hypothesis_id':'TENNIS_R4_10_PLUS7_5_V1','mode':'OUTCOME_BLIND_COMMON_WINDOW_RECONSTRUCTION','window':[START.isoformat(),END.isoformat()],'loaded_columns':USECOLS,'score_result_columns_loaded':False,'pregame_candidates_in_window':len(all_rows),'selected_legs':len(selected),'candidate_dates':len(counts),'date_leg_count_distribution':dict(sorted(Counter(counts.values()).items())),'three_leg_dates':sum(v>=3 for v in counts.values()),'rank_band':[LOW,HIGH],'opponent_rank_min':OPP_MIN,'max_per_date':MAX_DATE,'source_audit':audits}
    (OUT/'summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
