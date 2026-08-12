from __future__ import annotations

import hashlib, io, json, math, re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import requests

OUT=Path('artifacts/kira_tennis_r4_10_plus7_5_v1');OUT.mkdir(parents=True,exist_ok=True)
BLOCKS=[('DEV_2022',2022),('OOS_2023',2023)]
LOW_RANK=4;HIGH_RANK=10;OPP_MIN=30;MAX_DATE=3
REQ=['Date','Best of','Winner','Loser','WRank','LRank','W1','L1','W2','L2','W3','L3','Wsets','Lsets','Comment']

def wilson(w,n,z=1.959963984540054):
    if n<=0:return 0.0,1.0
    p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d;return max(0,c-m),min(1,c+m)
def clean(v):return re.sub(r'\s+',' ',str(v or '')).strip()
def num(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except:return None
def rank(v):
    x=num(v)
    if x is None or x<=0:return None
    return int(x)
def write_csv(path,rows):
    pd.DataFrame(rows).to_csv(path,index=False)
def download(year):
    s=requests.Session();s.headers['User-Agent']='KIRA-TENNIS-R4-10-P75/1.0 read-only'
    errors=[]
    for scheme in ('https','http'):
        url=f'{scheme}://www.tennis-data.co.uk/{year}/{year}.xlsx'
        try:
            r=s.get(url,timeout=90);r.raise_for_status();raw=r.content
            if len(raw)<1000:raise RuntimeError('WORKBOOK_TOO_SMALL')
            df=pd.read_excel(io.BytesIO(raw),sheet_name=str(year),engine='openpyxl')
            return df,{'year':year,'status':'PASS','scheme':scheme,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'url_path':f'/{year}/{year}.xlsx','rows':len(df),'columns':[str(x) for x in df.columns]}
        except Exception as exc:errors.append(f'{scheme}:{type(exc).__name__}')
    raise RuntimeError('TENNIS_DATA_DOWNLOAD_FAILED '+','.join(errors))
def normalize_date(v):
    try:
        d=pd.to_datetime(v,errors='coerce')
        if pd.isna(d):return ''
        return d.date().isoformat()
    except:return ''
def candidate_rows(df):
    missing=[c for c in REQ if c not in df.columns]
    if missing:raise RuntimeError('MISSING_REQUIRED_COLUMNS:'+','.join(missing))
    pre=[];status={}
    for idx,row in df.iterrows():
        try:best=int(float(row['Best of']))
        except:continue
        if best!=3:continue
        wr,lr=rank(row['WRank']),rank(row['LRank'])
        if wr is None or lr is None:continue
        winner,loser=clean(row['Winner']),clean(row['Loser'])
        if not winner or not loser:continue
        winner_sel=LOW_RANK<=wr<=HIGH_RANK and lr>=OPP_MIN
        loser_sel=LOW_RANK<=lr<=HIGH_RANK and wr>=OPP_MIN
        if winner_sel==loser_sel:continue
        selected=winner if winner_sel else loser;opp=loser if winner_sel else winner;sr=wr if winner_sel else lr;orr=lr if winner_sel else wr
        date=normalize_date(row['Date'])
        if not date:continue
        tour=clean(row.get('Tournament',''));rnd=clean(row.get('Round',''))
        identity=f'{date}|{winner}|{loser}|{tour}|{rnd}|{idx}'
        pre.append({'date':date,'source_row':int(idx),'winner':winner,'loser':loser,'selected_player':selected,'opponent':opp,'selected_rank':sr,'opponent_rank':orr,'tournament':tour,'round':rnd,'match_id':'TR475-'+hashlib.sha256(identity.encode()).hexdigest()[:20]})
        status[int(idx)]={'comment':clean(row['Comment']),'wsets':num(row['Wsets']),'lsets':num(row['Lsets']),'W1':num(row['W1']),'L1':num(row['L1']),'W2':num(row['W2']),'L2':num(row['L2']),'W3':num(row['W3']),'L3':num(row['L3'])}
    return pre,status
def rank_date(rows):
    return sorted(rows,key=lambda x:(x['selected_rank'],-x['opponent_rank'],x['selected_player'],x['opponent'],x['tournament'],x['round'],x['source_row']))[:MAX_DATE]
def settle(selected,status):
    settled=[];voids=[]
    for x in selected:
        st=status[x['source_row']]
        if st['comment'].casefold()!='completed':
            voids.append({**x,'comment':st['comment'],'settlement':'VOID_NONCOMPLETED'});continue
        wgames=0;lgames=0;sets=0;complete=True
        for i in (1,2,3):
            w=st[f'W{i}'];l=st[f'L{i}']
            if w is None and l is None:continue
            if w is None or l is None:complete=False;break
            wgames+=int(w);lgames+=int(l);sets+=1
        if not complete or sets<2:
            voids.append({**x,'comment':st['comment'],'settlement':'VOID_INCOMPLETE_SCORE'});continue
        selected_is_winner=x['selected_player']==x['winner'];sg=wgames if selected_is_winner else lgames;og=lgames if selected_is_winner else wgames
        settled.append({**x,'selected_games':sg,'opponent_games':og,'game_diff':sg-og,'hit':sg+7.5>og,'comment':st['comment']})
    return settled,voids
def score(label,year):
    bd=OUT/label.lower();bd.mkdir(parents=True,exist_ok=True)
    try:df,audit=download(year);pre,status=candidate_rows(df)
    except Exception as exc:
        r={'block':label,'year':year,'status':'SOURCE_GATE_FAIL','reason':f'{type(exc).__name__}:{exc}'};(bd/'summary.json').write_text(json.dumps(r,indent=2));return r
    by=defaultdict(list)
    for x in pre:by[x['date']].append(x)
    selected=[]
    for d,rr in sorted(by.items()):
        for rank_i,x in enumerate(rank_date(rr),1):selected.append({**x,'date_rank':rank_i})
    write_csv(bd/'selected_pre_settlement.csv',selected);ledger_sha=hashlib.sha256((bd/'selected_pre_settlement.csv').read_bytes()).hexdigest()
    settled,voids=settle(selected,status);write_csv(bd/'settled_legs.csv',settled);write_csv(bd/'voids.csv',voids);write_csv(bd/'failures.csv',[x for x in settled if not x['hit']])
    bundles_by=defaultdict(list)
    for x in settled:bundles_by[x['date']].append(x)
    bundles=[{'date':d,'legs':len(rr),'survived':all(x['hit'] for x in rr),'match_ids':'|'.join(x['match_id'] for x in rr)} for d,rr in sorted(bundles_by.items())]
    write_csv(bd/'daily_bundles.csv',bundles)
    nl=len(settled);wl=sum(bool(x['hit']) for x in settled);nd=len(bundles);wd=sum(bool(x['survived']) for x in bundles);lr=wl/nl if nl else 0;dr=wd/nd if nd else 0;ll,_=wilson(wl,nl);dl,_=wilson(wd,nd)
    gates={'source_schema_pass':True,'legs_ge_100':nl>=100,'dates_ge_70':nd>=70,'leg_rate_gt_90':lr>.90,'bundle_rate_gt_90':dr>.90,'unique_match_ids':len({x['match_id'] for x in selected})==len(selected),'max3_date':all(sum(1 for x in selected if x['date']==d)<=3 for d in by),'completed_settlement_only':all(x['comment'].casefold()=='completed' for x in settled)}
    r={'hypothesis_id':'TENNIS_R4_10_PLUS7_5_V1','block':label,'year':year,'status':'PASS' if all(gates.values()) else 'NO_PASS','pregame_candidates':len(pre),'selected_pre_settlement':len(selected),'voids':len(voids),'selected_legs':nl,'leg_wins':wl,'leg_rate':lr,'leg_wilson95_lcb':ll,'candidate_dates':nd,'bundle_wins':wd,'bundle_rate':dr,'bundle_wilson95_lcb':dl,'date_leg_count_distribution':dict(sorted(Counter(x['legs'] for x in bundles).items())),'selected_ledger_sha256':ledger_sha,'gates':gates,'source_audit':audit};(bd/'summary.json').write_text(json.dumps(r,indent=2,ensure_ascii=False));return r
def main():
    overall={'hypothesis_id':'TENNIS_R4_10_PLUS7_5_V1','blocks':[],'oos_opened':False};dev=score(*BLOCKS[0]);overall['blocks'].append(dev)
    if dev.get('status')!='PASS':overall['decision']='DEV_NO_PASS_CLOSED_OOS_UNOPENED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2));return
    overall['oos_opened']=True;oos=score(*BLOCKS[1]);overall['blocks'].append(oos);overall['decision']='OOS_CERTAINTY_PASS' if oos.get('status')=='PASS' else 'OOS_NO_PASS_CLOSED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2))
if __name__=='__main__':main()
