from __future__ import annotations
import json
from pathlib import Path
import kira_tennis_r4_10_plus7_5_v1 as base
HYPOTHESIS='TENNIS_R21_30_PLUS7_5_V1';OUT=Path('artifacts/kira_tennis_r21_30_plus7_5_v1');OUT.mkdir(parents=True,exist_ok=True)
BLOCKS=[('DEV_2018',2018),('OOS_2019',2019)]
base.OUT=OUT;base.LOW_RANK=21;base.HIGH_RANK=30;base.OPP_MIN=80;base.MAX_DATE=3

def run_block(label,year):
    result=base.score(label,year);result['hypothesis_id']=HYPOTHESIS
    (OUT/label.lower()/'summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');return result

def main():
    overall={'hypothesis_id':HYPOTHESIS,'preregistration':'prereg/TENNIS_R21_30_PLUS7_5_V1_2026-08-12.md','rank_band':[21,30],'opponent_rank_min':80,'line':'+7.5','blocks':[],'oos_opened':False}
    dev=run_block(*BLOCKS[0]);overall['blocks'].append(dev)
    if dev.get('status')!='PASS':overall['decision']='DEV_NO_PASS_CLOSED_OOS_UNOPENED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2,ensure_ascii=False));print(json.dumps(overall,indent=2,ensure_ascii=False));return
    overall['oos_opened']=True;oos=run_block(*BLOCKS[1]);overall['blocks'].append(oos);overall['decision']='OOS_CERTAINTY_PASS' if oos.get('status')=='PASS' else 'OOS_NO_PASS_CLOSED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2,ensure_ascii=False));print(json.dumps(overall,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
