from __future__ import annotations

import json
from pathlib import Path

SOURCE = Path(__file__).with_name('kira_mlb_team_runs_dev_2012.py')
text = SOURCE.read_text(encoding='utf-8')
text = text.replace('LINES = (3.5, 4.5)', 'LINES = (3.0, 4.0, 5.0, 6.0)')
text = text.replace('if len(configs) != 72:', 'if len(configs) != 144:')
ns = {'__name__': 'kira_mlb_team_runs_integer_v2_engine', '__file__': str(SOURCE)}
exec(compile(text, str(SOURCE), 'exec'), ns)
ns['OUT'] = Path('artifacts/kira_mlb_team_runs_integer_v2_dev_2012')

if __name__ == '__main__':
    rc = ns['main']()
    summary_path = ns['OUT'] / 'summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    summary['hypothesis_family'] = 'MLB_TEAM_RUNS_INTEGER_V2'
    summary['contract_lines'] = [3.0, 4.0, 5.0, 6.0]
    summary['equality_scored_as_failure'] = True
    summary['preregistration'] = 'MLB_TEAM_RUNS_INTEGER_V2_DEV_2012_PREREGISTRATION.md'
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding='utf-8')
    print('INTEGER_V2_FINAL')
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(rc)
