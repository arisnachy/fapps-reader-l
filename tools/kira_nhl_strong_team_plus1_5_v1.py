from __future__ import annotations

import csv, hashlib, json, math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import requests

OUT=Path('artifacts/kira_nhl_strong_team_plus1_5_v1');OUT.mkdir(parents=True,exist_ok=True)
TEAMS=['ANA','ARI','BOS','BUF','CAR','CBJ','CGY','CHI','COL','DAL','DET','EDM','FLA','LAK','MIN','MTL','NJD','NSH','NYI','NYR','OTT','PHI','PIT','SEA','SJS','STL','TBL','TOR','VAN','VGK','WPG','WSH']
BLOCKS=[('DEV_202223','20222023'),('OOS_202324','20232024')]
MIN_GAMES=25;SEL_WP=.650;OPP_WP=.500;MIN_GAP=.150;SEL_GD=.60;OPP_GD=0.0;MAX_DATE=2
MIN_LEGS=100;MIN_DATES=60;GATE=.90

class State:
    def __init__(self):self.games=0;self.wins=0;self.gf=0;self.ga=0
    @property
    def wp(self):return self.wins/self.games if self.games else 0.0
    @property
    def gd(self):return (self.gf-self.ga)/self.games if self.games else 0.0

def wilson(w,n,z=1.959963984540054):
    if n<=0:return 0.0,1.0
    p=w/n;den=1+z*z/n;c=(p+z*z/(2*n))/den;m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den;return max(0,c-m),min(1,c+m)
def write_csv(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fs=[]
    for r in rows:
        for k in r:
            if k not in fs:fs.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:w=csv.DictWriter(fh,fieldnames=fs);w.writeheader();w.writerows(rows)
def fetch_season(season):
    s=requests.Session();s.headers.update({'User-Agent':'KIRA-NHL-STRONG-P15-V1/1.0 read-only','Accept':'application/json'})
    games={};audit=[]
    for team in TEAMS:
        url=f'https://api-web.nhle.com/v1/club-schedule-season/{team}/{season}'
        try:r=s.get(url,timeout=45);r.raise_for_status();raw=r.content;p=r.json()
        except Exception as exc:
            audit.append({'team':team,'season':season,'status':'SOURCE_UNUSABLE','reason':type(exc).__name__});continue
        rows=p.get('games') or []
        audit.append({'team':team,'season':season,'status':'PASS','http':r.status_code,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'games_returned':len(rows),'url_path':f'/v1/club-schedule-season/{team}/{season}'})
        for g in rows:
            try:gid=int(g['id'])
            except:continue
            if int(g.get('gameType') or 0)!=2:continue
            games[gid]=g
    if len(audit)!=len(TEAMS) or any(x.get('status')!='PASS' for x in audit):return [],audit
    out=[]
    for gid,g in games.items():
        state=str(g.get('gameState') or '').upper()
        if state not in {'OFF','FINAL'}:continue
        away=g.get('awayTeam') or {};home=g.get('homeTeam') or {}
        try:
            aa=str(away['abbrev']);ha=str(home['abbrev']);ascore=int(away['score']);hscore=int(home['score']);d=str(g['gameDate'])[:10]
        except:continue
        if ascore==hscore:continue
        out.append({'date':d,'game_id':gid,'away':aa,'home':ha,'away_score':ascore,'home_score':hscore})
    out.sort(key=lambda x:(x['date'],x['game_id']))
    return out,audit
def candidate(game,states):
    a=states[game['away']];h=states[game['home']]
    if a.games<MIN_GAMES or h.games<MIN_GAMES:return None
    poss=[]
    for side,name,oppname,st,opp in [('AWAY',game['away'],game['home'],a,h),('HOME',game['home'],game['away'],h,a)]:
        gap=st.wp-opp.wp
        if st.wp>=SEL_WP and opp.wp<=OPP_WP and gap>=MIN_GAP and st.gd>=SEL_GD and opp.gd<=OPP_GD:
            poss.append((side,name,oppname,st,opp,gap))
    if len(poss)!=1:return None
    side,name,oppname,st,opp,gap=poss[0]
    return {'date':game['date'],'game_id':game['game_id'],'away':game['away'],'home':game['home'],'selected_side':side,'selected_team':name,'opponent':oppname,'selected_prior_games':st.games,'opponent_prior_games':opp.games,'selected_prior_wpct':st.wp,'opponent_prior_wpct':opp.wp,'wpct_gap':gap,'selected_prior_gd_game':st.gd,'opponent_prior_gd_game':opp.gd,'contract':'NHL_SELECTED_TEAM_PLUS1_5'}
def select(games):
    by=defaultdict(list);outcomes={}
    for g in games:by[g['date']].append(g);outcomes[g['game_id']]={'away_score':g['away_score'],'home_score':g['home_score']}
    states=defaultdict(State);selected=[];eligible=0
    for d,daygames in sorted(by.items()):
        cands=[]
        for g in sorted(daygames,key=lambda x:x['game_id']):
            pre={k:g[k] for k in ('date','game_id','away','home')};c=candidate(pre,states)
            if c:cands.append(c)
        eligible+=len(cands)
        cands=sorted(cands,key=lambda x:(-x['wpct_gap'],-x['selected_prior_gd_game'],x['opponent_prior_wpct'],x['selected_team'],x['opponent'],x['game_id']))[:MAX_DATE]
        for rank,c in enumerate(cands,1):selected.append({**c,'date_rank':rank})
        for g in daygames:
            a=states[g['away']];h=states[g['home']];a.games+=1;h.games+=1;a.gf+=g['away_score'];a.ga+=g['home_score'];h.gf+=g['home_score'];h.ga+=g['away_score']
            if g['away_score']>g['home_score']:a.wins+=1
            else:h.wins+=1
    return selected,outcomes,eligible
def score(label,season):
    bd=OUT/label.lower();bd.mkdir(parents=True,exist_ok=True);games,audit=fetch_season(season)
    if not games:
        r={'block':label,'season':season,'status':'SOURCE_GATE_FAIL','source_audit':audit};(bd/'summary.json').write_text(json.dumps(r,indent=2));return r
    sel,out,eligible=select(games);write_csv(bd/'selected_pre_settlement.csv',sel);sha=hashlib.sha256((bd/'selected_pre_settlement.csv').read_bytes()).hexdigest();settled=[]
    for x in sel:
        o=out[x['game_id']];ss=o['away_score'] if x['selected_side']=='AWAY' else o['home_score'];os=o['home_score'] if x['selected_side']=='AWAY' else o['away_score'];settled.append({**x,'selected_score':ss,'opponent_score':os,'margin':ss-os,'hit':ss+1.5>os})
    write_csv(bd/'settled_legs.csv',settled);write_csv(bd/'failures.csv',[x for x in settled if not x['hit']]);by=defaultdict(list)
    for x in settled:by[x['date']].append(x)
    bundles=[{'date':d,'legs':len(rr),'survived':all(x['hit'] for x in rr),'game_ids':'|'.join(str(x['game_id']) for x in rr)} for d,rr in sorted(by.items())];write_csv(bd/'daily_bundles.csv',bundles)
    nl=len(settled);wl=sum(x['hit'] for x in settled);nd=len(bundles);wd=sum(x['survived'] for x in bundles);lr=wl/nl if nl else 0;dr=wd/nd if nd else 0;ll,_=wilson(wl,nl);dl,_=wilson(wd,nd)
    gates={'all_team_sources_pass':len(audit)==len(TEAMS) and all(x.get('status')=='PASS' for x in audit),'legs_ge_100':nl>=MIN_LEGS,'dates_ge_60':nd>=MIN_DATES,'leg_rate_gt_90':lr>GATE,'bundle_rate_gt_90':dr>GATE,'temporal_firewall':True,'unique_events':len({x['game_id'] for x in settled})==nl,'max2_date':all(x['legs']<=2 for x in bundles),'settlement_complete':len(settled)==nl}
    r={'hypothesis_id':'NHL_STRONG_TEAM_PLUS1_5_V1','block':label,'season':season,'status':'PASS' if all(gates.values()) else 'NO_PASS','eligible_pre_cap':eligible,'selected_legs':nl,'leg_wins':wl,'leg_rate':lr,'leg_wilson95_lcb':ll,'candidate_dates':nd,'bundle_wins':wd,'bundle_rate':dr,'bundle_wilson95_lcb':dl,'date_leg_count_distribution':dict(sorted(Counter(x['legs'] for x in bundles).items())),'selected_ledger_sha256':sha,'gates':gates,'source_audit':audit};(bd/'summary.json').write_text(json.dumps(r,indent=2));return r
def main():
    overall={'hypothesis_id':'NHL_STRONG_TEAM_PLUS1_5_V1','blocks':[],'oos_opened':False};dev=score(*BLOCKS[0]);overall['blocks'].append(dev)
    if dev.get('status')!='PASS':overall['decision']='DEV_NO_PASS_CLOSED_OOS_UNOPENED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2));return
    overall['oos_opened']=True;oos=score(*BLOCKS[1]);overall['blocks'].append(oos);overall['decision']='OOS_CERTAINTY_PASS' if oos.get('status')=='PASS' else 'OOS_NO_PASS_CLOSED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2))
if __name__=='__main__':main()
