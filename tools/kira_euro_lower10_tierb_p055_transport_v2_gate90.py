from __future__ import annotations

import json
from pathlib import Path

import kira_euro_lower10_tierb_p055_transport_v1 as base

OUT=Path('artifacts/kira_euro_lower10_tierb_p055_transport_v2_gate90');OUT.mkdir(parents=True,exist_ok=True)


def main():
    # 2324 was not opened by V1 because V1 DEV stopped before OOS.
    oos=base.score('OOS_2324_GATE90','2324')
    gates={
        'source_gate': len(oos.get('source_audit') or [])==len(base.LEAGUES) and all(x.get('status')=='PASS' for x in (oos.get('source_audit') or [])),
        'selected_legs_ge_200': int(oos.get('selected_legs') or 0)>=200,
        'candidate_dates_ge_100': int(oos.get('candidate_dates') or 0)>=100,
        'leg_observed_rate_gt_90': float(oos.get('leg_rate') or 0)>0.90,
        'bundle_observed_rate_gt_90': float(oos.get('bundle_rate') or 0)>0.90,
        'duplicate_event_keys_zero': int(oos.get('duplicate_event_keys') or 0)==0,
        'max3_per_date': bool((oos.get('gates') or {}).get('max3_per_date')),
        'candidate_generation_outcome_blind': bool((oos.get('gates') or {}).get('candidate_generation_outcome_blind')),
        'settlement_complete': bool((oos.get('gates') or {}).get('settlement_complete')),
    }
    decision='OPERATIONAL_OOS_PASS' if all(gates.values()) else 'OOS_NO_PASS_V2_CLOSED'
    result={
        'hypothesis_id':'FOOTBALL_EURO_LOWER10_TIERB_P055_TRANSPORT_V2_GATE90',
        'preregistration':'prereg/FOOTBALL_EURO_LOWER10_TIERB_P055_TRANSPORT_V2_GATE90_2026-08-12.md',
        'selector_changed_from_v1':False,
        'line_changed_from_v1':False,
        'ranking_changed_from_v1':False,
        'oos_summary':oos,
        'user_gate90':gates,
        'wilson_is_diagnostic_not_veto':True,
        'decision':decision,
    }
    (OUT/'overall_summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
