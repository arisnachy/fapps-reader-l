from __future__ import annotations
import json
from pathlib import Path
import kira_tennis_r4_10_plus7_5_v1 as base

OUT=Path('artifacts/kira_tennis_r11_20_plus7_5_v2_gate90');OUT.mkdir(parents=True,exist_ok=True)
base.OUT=OUT;base.LOW_RANK=11;base.HIGH_RANK=20;base.OPP_MIN=50;base.MAX_DATE=3

def main():
    raw=base.score('OOS_2021_GATE90',2021)
    g=raw.get('gates') or {}
    gates={
        'source_schema_pass':bool(g.get('source_schema_pass')),
        'settled_legs_ge_50':int(raw.get('selected_legs') or 0)>=50,
        'candidate_dates_ge_40':int(raw.get('candidate_dates') or 0)>=40,
        'leg_observed_rate_gt_90':float(raw.get('leg_rate') or 0)>.90,
        'bundle_observed_rate_gt_90':float(raw.get('bundle_rate') or 0)>.90,
        'unique_match_ids':bool(g.get('unique_match_ids')),
        'max3_date':bool(g.get('max3_date')),
        'completed_settlement_only':bool(g.get('completed_settlement_only')),
    }
    result={'hypothesis_id':'TENNIS_R11_20_PLUS7_5_V2_GATE90','preregistration':'prereg/TENNIS_R11_20_PLUS7_5_V2_GATE90_2026-08-12.md','selector_changed_from_v1':False,'line_changed_from_v1':False,'target_year':2021,'raw_block_summary':raw,'user_gate90':gates,'wilson_is_diagnostic_not_veto':True,'decision':'OPERATIONAL_OOS_PASS' if all(gates.values()) else 'OOS_NO_PASS_V2_CLOSED'}
    (OUT/'overall_summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
