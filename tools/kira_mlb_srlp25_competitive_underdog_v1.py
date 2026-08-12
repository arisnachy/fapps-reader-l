from __future__ import annotations
import csv,hashlib,json,math
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path
import kira_mlb_srlp25_standings_gap_v1 as base

OUT=Path('artifacts/kira_mlb_srlp25_competitive_underdog_v1');OUT.mkdir(parents=True,exist_ok=True)
BLOCKS=[('DEV_2023',2023,date(2023,3,1),date(2023,11,15)),('OOS_2024',2024,date(2024,3,1),date(2024,11,15))]
MAXD=2

def wilson(w,n,z=1.959963984540054):
    if not n:return 0.0,1.0
    p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d;return max(0,c-m),min(1,c+m)
def write(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fs=[]
    for r in rows:
        for k in r:
            if k not in fs:fs.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:w=csv.DictWriter(fh,fieldnames=fs);w.writeheader();w.writerows(rows)
def candidate(game,states):
    a=states[int(game['away_id'])];h=states[int(game['home_id'])]
    if a.games<40 or h.games<40 or a.wpct==h.wpct:return None
    if a.wpct<h.wpct:
        side='AWAY';sel=a;opp=h;sel_id=int(game['away_id']);opp_id=int(game['home_id']);sel_name=game['away_name'];opp_name=game['home_name']
    else:
        side='HOME';sel=h;opp=a;sel_id=int(game['home_id']);opp_id=int(game['away_id']);sel_name=game['home_name'];opp_name=game['away_name']
    gap=opp.wpct-sel.wpct
    if not (.400<=sel.wpct<.500 and .500<opp.wpct<=.600 and .040<=gap<=.120 and sel.rdg>=-.60 and opp.rdg<=.80):return None
    return {'date':game['date'],'game_pk':game['game_pk'],'away_id':game['away_id'],'away_name':game['away_name'],'home_id':game['home_id'],'home_name':game['home_name'],'selected_id':sel_id,'selected_name':sel_name,'opponent_id':opp_id,'opponent_name':opp_name,'selected_side':side,'selected_prior_games':sel.games,'opponent_prior_games':opp.games,'selected_prior_wpct':sel.wpct,'opponent_prior_wpct':opp.wpct,'prior_wpct_gap':gap,'selected_prior_rdg':sel.rdg,'opponent_prior_rdg':opp.rdg,'contract':'JUANCITO_MLB_SUPER_RUN_LINE_SELECTED_PLUS2_5'}
def select(games):
    states=defaultdict(base.TeamState);by=defaultdict(list);outcomes={}
    for g in games:by[g['date']].append(g);outcomes[int(g['game_pk'])]={'away_score':int(g['away_score']),'home_score':int(g['home_score'])}
    selected=[];eligible=0
    for d,daygames in sorted(by.items()):
        cands=[]
        for g in sorted(daygames,key=lambda x:int(x['game_pk'])):
            pre={k:g[k] for k in ('date','game_pk','away_id','away_name','home_id','home_name')};c=candidate(pre,states)
            if c:cands.append(c)
        eligible+=len(cands);cands=sorted(cands,key=lambda x:(x['prior_wpct_gap'],-x['selected_prior_rdg'],x['opponent_prior_rdg'],x['selected_name'],x['opponent_name'],x['game_pk']))[:MAXD]
        for rank,c in enumerate(cands,1):selected.append({**c,'date_rank':rank})
        base.update_states_for_day(daygames,states)
    return selected,outcomes,eligible
def score(label,year,start,end):
    bd=OUT/label.lower();bd.mkdir(parents=True,exist_ok=True);games,audit=base.fetch_block(year,start,end);sel,out,eligible=select(games);write(bd/'selected_pre_settlement.csv',sel);sha=hashlib.sha256((bd/'selected_pre_settlement.csv').read_bytes()).hexdigest();settled=[]
    for x in sel:
        o=out[int(x['game_pk'])];ss=o['away_score'] if x['selected_side']=='AWAY' else o['home_score'];os=o['home_score'] if x['selected_side']=='AWAY' else o['away_score'];settled.append({**x,'selected_score':ss,'opponent_score':os,'selected_margin':ss-os,'hit':ss-os>=-2})
    write(bd/'settled_legs.csv',settled);write(bd/'failures.csv',[x for x in settled if not x['hit']]);byd=defaultdict(list)
    for x in settled:byd[x['date']].append(x)
    bundles=[{'date':d,'legs':len(rr),'survived':all(x['hit'] for x in rr),'game_pks':'|'.join(str(x['game_pk']) for x in rr)} for d,rr in sorted(byd.items())];write(bd/'daily_bundles.csv',bundles)
    nl=len(settled);wl=sum(x['hit'] for x in settled);nd=len(bundles);wd=sum(x['survived'] for x in bundles);lr=wl/nl if nl else 0;dr=wd/nd if nd else 0;ll,_=wilson(wl,nl);dl,_=wilson(wd,nd)
    gates={'legs_ge_100':nl>=100,'dates_ge_60':nd>=60,'leg_rate_gt_90':lr>.90,'bundle_rate_gt_90':dr>.90,'temporal_firewall':True,'unique_events':len({x['game_pk'] for x in settled})==nl,'max2_date':all(x['legs']<=2 for x in bundles),'settlement_complete':len(settled)==nl}
    r={'hypothesis_id':'MLB_SRLP25_COMPETITIVE_UNDERDOG_V1','block':label,'year':year,'status':'PASS' if all(gates.values()) else 'NO_PASS','eligible_pre_cap':eligible,'selected_legs':nl,'leg_wins':wl,'leg_rate':lr,'leg_wilson95_lcb':ll,'candidate_dates':nd,'bundle_wins':wd,'bundle_rate':dr,'bundle_wilson95_lcb':dl,'date_leg_count_distribution':dict(sorted(Counter(x['legs'] for x in bundles).items())),'selected_ledger_sha256':sha,'gates':gates,'source_audit':audit};(bd/'summary.json').write_text(json.dumps(r,indent=2));return r
def main():
    overall={'hypothesis_id':'MLB_SRLP25_COMPETITIVE_UNDERDOG_V1','blocks':[],'oos_opened':False};dev=score(*BLOCKS[0]);overall['blocks'].append(dev)
    if dev.get('status')!='PASS':overall['decision']='DEV_NO_PASS_CLOSED_OOS_UNOPENED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2));return
    overall['oos_opened']=True;oos=score(*BLOCKS[1]);overall['blocks'].append(oos);overall['decision']='OOS_CERTAINTY_PASS' if oos.get('status')=='PASS' else 'OOS_NO_PASS_CLOSED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2))
if __name__=='__main__':main()
