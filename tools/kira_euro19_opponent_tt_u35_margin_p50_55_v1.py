from __future__ import annotations
import csv,hashlib,json,math
from collections import Counter,defaultdict
from pathlib import Path
import kira_euro19_opponent_tt_u35_broad_v1 as base

OUT=Path('artifacts/kira_euro19_opponent_tt_u35_margin_p50_55_v1');OUT.mkdir(parents=True,exist_ok=True)
BLOCKS=[('DEV_2021','2021'),('OOS_2122','2122')];LOW=.50;HIGH=.55;MAXD=3

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
def score(label,season):
    bd=OUT/label.lower();bd.mkdir(parents=True,exist_ok=True);pre,out,audit=base.fetch(season);source_ok=len(audit)==len(base.LEAGUES) and all(x.get('status')=='PASS' for x in audit)
    marginal=[x for x in pre if LOW<=float(x['p_selected_novig'])<HIGH]
    if not source_ok:
        r={'block':label,'season':season,'status':'SOURCE_GATE_FAIL','source_audit':audit};(bd/'summary.json').write_text(json.dumps(r,indent=2));return r
    by=defaultdict(list)
    for x in marginal:by[x['date']].append(x)
    sel=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(-x['p_selected_novig'],x['selected_price'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:MAXD]
        for rank,x in enumerate(rr,1):sel.append({**x,'date_rank':rank})
    write(bd/'selected_pre_settlement.csv',sel);sha=hashlib.sha256((bd/'selected_pre_settlement.csv').read_bytes()).hexdigest();settled=[]
    for x in sel:
        o=out[x['event_id']];opp_goals=o['away_goals'] if x['selected_side']=='HOME' else o['home_goals'];settled.append({**x,**o,'opponent_goals':opp_goals,'hit':opp_goals<=3})
    write(bd/'settled_legs.csv',settled);write(bd/'failures.csv',[x for x in settled if not x['hit']]);byd=defaultdict(list)
    for x in settled:byd[x['date']].append(x)
    bundles=[{'date':d,'legs':len(rr),'survived':all(x['hit'] for x in rr),'event_ids':'|'.join(x['event_id'] for x in rr)} for d,rr in sorted(byd.items())];write(bd/'daily_bundles.csv',bundles);write(bd/'bundle_failures.csv',[x for x in bundles if not x['survived']])
    nl=len(settled);wl=sum(x['hit'] for x in settled);nd=len(bundles);wd=sum(x['survived'] for x in bundles);lr=wl/nl if nl else 0;dr=wd/nd if nd else 0;ll,_=wilson(wl,nl);dl,_=wilson(wd,nd)
    gates={'all19_sources_pass':source_ok,'legs_ge_300':nl>=300,'dates_ge_150':nd>=150,'leg_rate_gt_90':lr>.90,'bundle_rate_gt_90':dr>.90,'outcome_blind':True,'unique_events':len({x['event_id'] for x in settled})==nl,'max3_date':all(x['legs']<=3 for x in bundles),'settlement_complete':len(settled)==nl}
    r={'hypothesis_id':'FOOTBALL_EURO19_OPPONENT_TT_U35_MARGIN_P50_55_V1','block':label,'season':season,'status':'PASS' if all(gates.values()) else 'NO_PASS','eligible_band_pre_cap':len(marginal),'selected_legs':nl,'leg_wins':wl,'leg_rate':lr,'leg_wilson95_lcb':ll,'candidate_dates':nd,'bundle_wins':wd,'bundle_rate':dr,'bundle_wilson95_lcb':dl,'date_leg_count_distribution':dict(sorted(Counter(x['legs'] for x in bundles).items())),'selected_ledger_sha256':sha,'gates':gates,'source_audit':audit,'frozen_band':[LOW,HIGH]};(bd/'summary.json').write_text(json.dumps(r,indent=2));return r
def main():
    overall={'hypothesis_id':'FOOTBALL_EURO19_OPPONENT_TT_U35_MARGIN_P50_55_V1','blocks':[],'oos_opened':False};dev=score(*BLOCKS[0]);overall['blocks'].append(dev)
    if dev.get('status')!='PASS':overall['decision']='DEV_NO_PASS_CLOSED_OOS_UNOPENED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2));return
    overall['oos_opened']=True;oos=score(*BLOCKS[1]);overall['blocks'].append(oos);overall['decision']='OOS_CERTAINTY_PASS' if oos.get('status')=='PASS' else 'OOS_NO_PASS_CLOSED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2))
if __name__=='__main__':main()
