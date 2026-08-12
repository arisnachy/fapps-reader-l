from __future__ import annotations

import io,json
from collections import defaultdict,Counter
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT=Path('artifacts/kira_nba_floor90_calendar_2025'); OUT.mkdir(parents=True,exist_ok=True)
URL='https://raw.githubusercontent.com/llimllib/nba_data/main/data/gamelog_2025.parquet'
START=date(2025,1,1); END=date(2025,3,31)
UA={'User-Agent':'KIRA-NBA-FLOOR90-calendar-2025/1.0'}

def pick(df,names):
    lu={str(c).upper():str(c) for c in df.columns}
    for n in names:
        if n.upper() in lu:return lu[n.upper()]
    raise RuntimeError(f'MISSING {names}')

def load():
    r=requests.get(URL,headers=UA,timeout=120);r.raise_for_status();raw=r.content
    log=pd.read_parquet(io.BytesIO(raw))
    cg=pick(log,['GAME_ID','game_id']);cd=pick(log,['GAME_DATE','game_date']);ct=pick(log,['TEAM_NAME','team_name']);cp=pick(log,['PTS','pts']);cm=pick(log,['MATCHUP','matchup'])
    d=log[[cg,cd,ct,cp,cm]].copy();d.columns=['game_id','game_date','team','pts','matchup']
    d.game_id=d.game_id.astype(str).str.replace(r'\.0$','',regex=True).str.zfill(10);d=d[d.game_id.str.startswith('002')]
    d.game_date=pd.to_datetime(d.game_date,errors='coerce');d.pts=pd.to_numeric(d.pts,errors='coerce');d=d[d.game_date.notna()&d.pts.notna()]
    rows=[]
    for gid,g in d.groupby('game_id'):
        if len(g)!=2:continue
        h=g[g.matchup.astype(str).str.contains('vs',case=False,regex=False)];a=g[g.matchup.astype(str).str.contains('@',regex=False)]
        if len(h)!=1 or len(a)!=1:continue
        H=h.iloc[0];A=a.iloc[0]
        rows.append({'date':pd.Timestamp(H.game_date).normalize(),'home':str(H.team),'away':str(A.team),'home_pts':int(H.pts),'away_pts':int(A.pts),'game_id':str(gid)})
    return pd.DataFrame(rows).sort_values(['date','game_id']).drop_duplicates('game_id')

def select(games,target):
    ts=pd.Timestamp(target);prior=games[games.date<ts];today=games[games.date==ts]
    th=defaultdict(list);oa=defaultdict(list)
    for _,r in prior.sort_values('date').iterrows():
        th[r.home].append(int(r.home_pts));th[r.away].append(int(r.away_pts));oa[r.home].append(int(r.away_pts));oa[r.away].append(int(r.home_pts))
    c=[]
    for _,r in today.iterrows():
        for side,team,opp in [('HOME',r.home,r.away),('AWAY',r.away,r.home)]:
            h=th.get(team,[]);oh=oa.get(opp,[])
            if len(h)<15 or len(oh)<15:continue
            arr=np.asarray(h,float);o=np.asarray(oh,float);q10=float(np.quantile(arr,.10,method='linear'));below=float(np.mean(arr<90));last10=float(np.mean(arr[-10:]));opph=float(np.mean(o<90));med=float(np.median(arr))
            if q10<92 or below>.05 or last10<105 or opph>.10:continue
            c.append({'date':target.isoformat(),'event_id':str(r.game_id),'side':side,'team':team,'opponent':opp,'q10':q10,'below90_rate':below,'last10_mean':last10,'opp_hold_below90_rate':opph,'median':med})
    c.sort(key=lambda x:(-x['q10'],x['below90_rate'],-x['median'],-x['last10_mean'],x['team']))
    return c[:2]

def main():
    games=load();selected=[]
    for d in pd.date_range(START,END,freq='D'):selected.extend(select(games,d.date()))
    df=pd.DataFrame(selected);df.to_csv(OUT/'nba_floor90_selected_2025.csv',index=False)
    raw_counts=Counter(df.date.tolist()) if not df.empty else Counter()
    ded=df.drop_duplicates(['date','event_id'],keep='first').copy() if not df.empty else df
    ded.to_csv(OUT/'nba_floor90_event_deduped_2025.csv',index=False)
    counts=Counter(ded.date.tolist()) if not ded.empty else Counter()
    summary={'window':[START.isoformat(),END.isoformat()],'calendar_days':(END-START).days+1,'raw_selected_team_legs':int(len(df)),'raw_candidate_dates':len(raw_counts),'raw_date_leg_distribution':dict(sorted(Counter(raw_counts.values()).items())),'event_deduped_legs':int(len(ded)),'event_deduped_candidate_dates':len(counts),'event_deduped_date_leg_distribution':dict(sorted(Counter(counts.values()).items())),'selector':'>=15 prior; q10>=92; below90<=.05; last10>=105; opponent hold-below90<=.10; deterministic rank; max2/day','target_day_scores_used_for_selection':False,'settlement_scored_here':False}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
