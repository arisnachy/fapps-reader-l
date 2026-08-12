from __future__ import annotations

import io,json,math
from collections import defaultdict,Counter
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT=Path('artifacts/kira_wnba_c3_calendar_2025'); OUT.mkdir(parents=True,exist_ok=True)
API='https://api.github.com/repos/sportsdataverse/sportsdataverse-data/releases/tags/espn_wnba_schedules'
UA={'User-Agent':'KIRA-WNBA-C3-calendar-2025/1.0'}
YEAR=2025; START=date(2025,6,1); END=date(2025,8,31)


def assets():
    r=requests.get(API,headers=UA,timeout=60); r.raise_for_status()
    return {a['name']:a['browser_download_url'] for a in r.json().get('assets',[])}

def load_full_year(amap):
    name=f'wnba_schedule_{YEAR}.parquet'; r=requests.get(amap[name],headers=UA,timeout=120); r.raise_for_status()
    raw=r.content; d=pd.read_parquet(io.BytesIO(raw))
    cols=['game_id','game_date','season_type','status_type_completed','home_display_name','away_display_name','home_score','away_score']
    missing=[c for c in cols if c not in d.columns]
    if missing: raise RuntimeError(f'MISSING_COLUMNS={missing}')
    d=d[cols].copy();d['date']=pd.to_datetime(d.game_date,errors='coerce')
    d.home_score=pd.to_numeric(d.home_score,errors='coerce');d.away_score=pd.to_numeric(d.away_score,errors='coerce')
    comp=d.status_type_completed.astype(str).str.lower().isin(['true','1'])
    d=d[(pd.to_numeric(d.season_type,errors='coerce')==2)&comp&d.date.notna()&d.home_score.notna()&d.away_score.notna()].copy()
    d=d[(d.date.dt.year==YEAR)&(d.date.dt.date<=END)].sort_values('date')
    return d,raw

def select(games):
    targets=sorted(games[(games.date.dt.date>=START)&(games.date.dt.date<=END)].date.dt.date.unique())
    selected=[];universe=[]
    for target in targets:
        prior=games[games.date<pd.Timestamp(target)]
        today=games[games.date.dt.date==target]
        scored=defaultdict(list);allowed=defaultdict(list)
        for _,r in prior.iterrows():
            scored[r.home_display_name].append(int(r.home_score));scored[r.away_display_name].append(int(r.away_score))
            allowed[r.home_display_name].append(int(r.away_score));allowed[r.away_display_name].append(int(r.home_score))
        cand=[]
        for _,r in today.iterrows():
            for side,team,opp in [('HOME',r.home_display_name,r.away_display_name),('AWAY',r.away_display_name,r.home_display_name)]:
                h=scored.get(team,[]);oh=allowed.get(opp,[])
                if len(h)<8 or len(oh)<8:continue
                arr=np.asarray(h,float);o=np.asarray(oh,float)
                q10=float(np.quantile(arr,.10,method='linear'));below=float(np.mean(arr<55));last5=float(np.mean(arr[-5:]));med=float(np.median(arr));opphold=float(np.mean(o<55))
                if q10<59 or below>0.05 or last5<65 or opphold>0.10:continue
                row={'date':target.isoformat(),'event_id':str(r.game_id),'side':side,'team':team,'opponent':opp,'q10':q10,'below55_rate':below,'last5_mean':last5,'median':med,'opp_hold_below55_rate':opphold}
                cand.append(row);universe.append(row)
        cand.sort(key=lambda x:(-x['q10'],x['below55_rate'],-x['median'],-x['last5_mean'],x['team']))
        for rank,x in enumerate(cand[:2],1):selected.append({**x,'rank':rank})
    return pd.DataFrame(universe),pd.DataFrame(selected),targets

def main():
    amap=assets();games,raw=load_full_year(amap);univ,sel,targets=select(games)
    univ.to_csv(OUT/'wnba_c3_universe_2025.csv',index=False);sel.to_csv(OUT/'wnba_c3_selected_2025.csv',index=False)
    cnt=Counter(sel['date'].tolist()) if not sel.empty else Counter()
    event_dups=int(sel.duplicated(['date','event_id']).sum()) if not sel.empty else 0
    summary={'hypothesis':'WNBA_C3_FLOOR55_SEASON_HISTORY','year':YEAR,'target_window':[START.isoformat(),END.isoformat()],'full_regular_games_through_aug31':int(len(games)),'target_game_dates':len(targets),'candidate_dates':len(cnt),'selected_legs':int(len(sel)),'date_leg_count_distribution':dict(sorted(Counter(cnt.values()).items())),'same_event_duplicate_selected_rows':event_dups,'selector':'prior-only >=8; q10>=59; below55<=.05; last5>=65; opponent hold-below55<=.10; deterministic rank; max2/date','target_day_scores_used_for_selection':False,'settlement_scored_here':False}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
