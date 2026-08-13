from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

OUT = Path('artifacts/kira_extra16_plus1_5_maxn_2021')
OUT.mkdir(parents=True, exist_ok=True)
CODES = ['ARG','AUT','BRA','CHN','DNK','FIN','IRL','JPN','MEX','NOR','POL','ROU','RUS','SWE','SWZ','USA']
REQ = ['Date','Home','Away','League','AvgCH','AvgCD','AvgCA','HG','AG']
YEAR = 2021
TH = 0.60
MAX_N = 7
NS = [3,4,5,6,7]
MIN_DATES = 35
OBS_FLOOR = 0.90
TARGET = 0.92
WILSON_FLOOR = 0.90


def wilson(w, n, z=1.959963984540054):
    if n <= 0:
        return 0.0, 1.0
    p = w / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    m = z*math.sqrt((p*(1-p) + z*z/(4*n))/n)/d
    return max(0.0, c-m), min(1.0, c+m)


def pdate(s):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:
            return datetime.strptime(str(s).strip(), f).date()
        except Exception:
            pass
    return None


def write(path, rows):
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    fields = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    sess = requests.Session()
    sess.headers['User-Agent'] = 'KIRA-EXTRA16-MAXN-2021/1.0'
    audit = []
    pre = []
    outcomes = {}
    seen = set()
    dups = 0

    for code in CODES:
        url = f'https://www.football-data.co.uk/new/{code}.csv'
        try:
            r = sess.get(url, timeout=60)
            r.raise_for_status()
        except Exception as exc:
            audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':type(exc).__name__})
            continue
        raw = r.content
        rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig', errors='replace'))))
        if not rows:
            audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':'EMPTY'})
            continue
        h = [x.strip() for x in rows[0]]
        miss = [c for c in REQ if c not in h]
        if miss:
            audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':'MISSING_COLUMNS','missing':miss})
            continue
        idx = {c:h.index(c) for c in REQ}
        mx = max(idx.values())
        serial = []
        eligible = 0
        for row in rows[1:]:
            if len(row) <= mx:
                continue
            d = pdate(row[idx['Date']])
            if d is None or d.year != YEAR:
                continue
            serial.append(','.join(row))
            home = row[idx['Home']].strip()
            away = row[idx['Away']].strip()
            league = row[idx['League']].strip()
            try:
                h1 = float(row[idx['AvgCH']]); dr = float(row[idx['AvgCD']]); a1 = float(row[idx['AvgCA']])
                hg = int(float(row[idx['HG']])); ag = int(float(row[idx['AG']]))
            except Exception:
                continue
            if not home or not away or not all(math.isfinite(x) and x > 1 for x in (h1,dr,a1)):
                continue
            qh, qd, qa = 1/h1, 1/dr, 1/a1
            den = qh + qd + qa
            ph, pa = qh/den, qa/den
            if ph == pa:
                continue
            side = 'HOME' if ph > pa else 'AWAY'
            prob = max(ph, pa)
            if prob < TH:
                continue
            price = h1 if side == 'HOME' else a1
            ent = home if side == 'HOME' else away
            key = (d.isoformat(), code, league, home, away)
            if key in seen:
                dups += 1
                continue
            seen.add(key)
            eid = 'X16-' + hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            pre.append({
                'date':d.isoformat(),'source':code,'league':league,'Home':home,'Away':away,
                'selected_side':side,'selected_entity':ent,'selected_price':price,
                'p_favorite_novig':prob,'event_id':eid
            })
            # Outcomes are stored separately and never enter eligibility/ranking.
            outcomes[eid] = {'HG':hg,'AG':ag}
            eligible += 1
        audit.append({
            'source':code,'status':'PASS','file_sha256':hashlib.sha256(raw).hexdigest(),
            'target_rows_sha256':hashlib.sha256('\n'.join(serial).encode()).hexdigest(),
            'target_rows':len(serial),'eligible_pre_cap':eligible
        })

    if len(audit) != len(CODES) or any(x.get('status') != 'PASS' for x in audit):
        res = {'decision':'SOURCE_GATE_FAIL','source_audit':audit}
        (OUT/'summary.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
        print(json.dumps(res, indent=2))
        return
    if dups:
        raise SystemExit(f'DUPLICATES={dups}')

    by = {}
    for x in pre:
        by.setdefault(x['date'], []).append(x)

    frozen = []
    full_date_counts = {}
    for d, rr in sorted(by.items()):
        rr = sorted(rr, key=lambda x:(
            -x['p_favorite_novig'], x['selected_price'], x['source'], x['league'],
            x['Home'], x['Away'], 0 if x['selected_side']=='HOME' else 1
        ))
        full_date_counts[d] = len(rr)
        for rank, x in enumerate(rr[:MAX_N], 1):
            frozen.append({**x, 'date_rank':rank, 'eligible_count_on_date':len(rr)})

    # Freeze all rank-1..7 event identities BEFORE settlement.
    write(OUT/'maxn_event_keys_pre_settlement.csv', frozen)
    ledger_sha = hashlib.sha256((OUT/'maxn_event_keys_pre_settlement.csv').read_bytes()).hexdigest()

    settled = []
    for x in frozen:
        o = outcomes[x['event_id']]
        gd = (o['HG']-o['AG']) if x['selected_side']=='HOME' else (o['AG']-o['HG'])
        settled.append({**x, **o, 'selected_goal_diff':gd, 'hit':gd + 1.5 > 0})
    write(OUT/'maxn_rank1_7_settled.csv', settled)

    sd = {}
    for x in settled:
        sd.setdefault(x['date'], []).append(x)
    for d in sd:
        sd[d] = sorted(sd[d], key=lambda x:x['date_rank'])

    per_n = {}
    failed_tickets_all = []
    failed_legs_all = []
    for n in NS:
        tickets = []
        selected_rows = []
        for d in sorted(sd):
            if full_date_counts[d] < n:
                continue
            rr = sd[d][:n]
            if len(rr) != n:
                raise RuntimeError(f'prefix freeze mismatch {d} N={n}')
            survived = all(bool(x['hit']) for x in rr)
            tickets.append({
                'N':n,'date':d,'survived':survived,
                'event_ids':'|'.join(x['event_id'] for x in rr),
                'entities':'|'.join(x['selected_entity'] for x in rr)
            })
            selected_rows.extend({**x, 'ticket_N':n} for x in rr)
            if not survived:
                failed_tickets_all.append(tickets[-1])
                failed_legs_all.extend({**x, 'ticket_N':n} for x in rr if not bool(x['hit']))
        nd = len(tickets)
        wd = sum(bool(x['survived']) for x in tickets)
        dl, du = wilson(wd, nd)
        nl = len(selected_rows)
        wl = sum(bool(x['hit']) for x in selected_rows)
        ll, lu = wilson(wl, nl)
        obs = wd/nd if nd else 0.0
        per_n[str(n)] = {
            'N':n,
            'evaluable_dates':nd,
            'ticket_wins':wd,
            'ticket_losses':nd-wd,
            'ticket_survival':obs,
            'ticket_wilson95_lcb':dl,
            'ticket_wilson95_ucb':du,
            'prefix_leg_observations':nl,
            'prefix_leg_wins':wl,
            'prefix_leg_losses':nl-wl,
            'prefix_leg_survival':wl/nl if nl else 0.0,
            'prefix_leg_wilson95_lcb':ll,
            'prefix_leg_wilson95_ucb':lu,
            'observed_floor_pass':nd>=MIN_DATES and obs>OBS_FLOOR,
            'target_92_pass':nd>=MIN_DATES and obs>TARGET,
            'strong_wilson_signal':nd>=MIN_DATES and dl>=WILSON_FLOOR,
            'evidence_too_thin':nd<MIN_DATES,
        }
        write(OUT/f'tickets_N{n}.csv', tickets)

    eligible_winners = [
        int(n) for n, m in per_n.items()
        if (not m['evidence_too_thin']) and m['ticket_survival']>OBS_FLOOR and m['ticket_wilson95_lcb']>=WILSON_FLOOR
    ]
    maxn_winner = max(eligible_winners) if eligible_winners else None

    distribution = Counter(min(v, MAX_N) for v in full_date_counts.values())
    res = {
        'hypothesis_id':'MAXN_EXTRA16_FAVORITE_PLUS1_5_2021_STRESS_TEST',
        'status':'RETROSPECTIVE_ONLY',
        'preregistration':'MAXN_EXTRA16_PLUS1_5_2021_PREREGISTRATION.md',
        'year':YEAR,'threshold':TH,'max_n':MAX_N,'sources':CODES,
        'candidate_generation_used_outcomes':False,
        'duplicate_event_keys':dups,
        'pre_settlement_ledger_sha256':ledger_sha,
        'eligible_dates_any':len(full_date_counts),
        'full_candidate_count_distribution_capped7':dict(sorted(distribution.items())),
        'per_n':per_n,
        'maxn_historical_stress_winner':maxn_winner,
        'production_valid':False,
        'production_note':'Requires independent/prospective confirmation; 2021 was previously used by MULTI3.',
        'source_audit':audit,
    }
    write(OUT/'failed_tickets_all_N.csv', failed_tickets_all)
    write(OUT/'failed_legs_all_N.csv', failed_legs_all)
    (OUT/'summary.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    (OUT/'source_audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    print(json.dumps(res, indent=2))

if __name__ == '__main__':
    main()
