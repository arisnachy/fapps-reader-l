from __future__ import annotations

import json
from pathlib import Path

import kira_tennis_r4_10_plus7_5_v1 as base

HYPOTHESIS='TENNIS_R11_20_PLUS7_5_V1'
OUT=Path('artifacts/kira_tennis_r11_20_plus7_5_v1');OUT.mkdir(parents=True,exist_ok=True)
BLOCKS=[('DEV_2020',2020),('OOS_2021',2021)]

# Reuse the already-audited exact-date +7.5 engine while changing only the prospectively
# frozen rank population and artifact root. The engine reads these globals dynamically.
base.OUT=OUT
base.LOW_RANK=11
base.HIGH_RANK=20
base.OPP_MIN=50
base.MAX_DATE=3


def run_block(label: str, year: int):
    result=base.score(label,year)
    result['hypothesis_id']=HYPOTHESIS
    path=OUT/label.lower()/'summary.json'
    path.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    return result


def main():
    overall={'hypothesis_id':HYPOTHESIS,'preregistration':'prereg/TENNIS_R11_20_PLUS7_5_V1_2026-08-12.md','rank_band':[11,20],'opponent_rank_min':50,'line':'+7.5','blocks':[],'oos_opened':False}
    dev=run_block(*BLOCKS[0]);overall['blocks'].append(dev)
    if dev.get('status')!='PASS':
        overall['decision']='DEV_NO_PASS_CLOSED_OOS_UNOPENED'
        (OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2,ensure_ascii=False),encoding='utf-8')
        print(json.dumps(overall,indent=2,ensure_ascii=False));return
    overall['oos_opened']=True
    oos=run_block(*BLOCKS[1]);overall['blocks'].append(oos)
    overall['decision']='OOS_CERTAINTY_PASS' if oos.get('status')=='PASS' else 'OOS_NO_PASS_CLOSED'
    (OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(overall,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
