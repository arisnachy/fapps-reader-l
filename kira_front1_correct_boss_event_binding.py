from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

SRC = Path('front1_football_contract_inventory_v2/football_market_actions.jsonl')
OUT = Path('front1_football_contract_inventory_v2/boss_event_binding_audit.json')

ID_RE = re.compile(r'^(SZ)?(ML|PS|TT)_(\d+)_(\d+)$')
HALF_RE = re.compile(r'(?i)(?:\b1H\b|1st\s+Half|first\s+half|primera\s+mitad|primer\s+tiempo)')
FRACTIONS = {'¼': 0.25, '½': 0.5, '¾': 0.75}

def clean(v):
    return re.sub(r'\s+', ' ', str(v or '')).strip()

def number_with_fraction(raw: str):
    raw = clean(raw)
    if not raw:
        return None
    sign = -1 if raw.startswith('-') else 1
    s = raw.lstrip('+-')
    try:
        if s in FRACTIONS:
            return sign * FRACTIONS[s]
        if s[-1:] in FRACTIONS:
            whole = s[:-1]
            return sign * ((float(whole) if whole else 0.0) + FRACTIONS[s[-1]])
        return sign * float(s)
    except Exception:
        return None

def parse_market_line(family: str, text: str):
    text = clean(text)
    if family == 'PS':
        # BOSS participant-spread text is e.g. '-½ +143', '+½ -193', '+1½ -110'.
        m = re.match(r'^([+-]?(?:\d+)?[¼½¾]|[+-]?\d+(?:\.\d+)?)\s+[+-]\d{3,4}$', text)
        return number_with_fraction(m.group(1)) if m else None
    if family == 'TT':
        # BOSS game-total text is e.g. 'O 2½ +103', 'U 1 -113'.
        m = re.match(r'^[OU]\s+((?:\d+)?[¼½¾]|\d+(?:\.\d+)?)\s+[+-]\d{3,4}$', text, re.I)
        return number_with_fraction(m.group(1)) if m else None
    return None

rows = []
for line in SRC.read_text(encoding='utf-8').splitlines():
    if line.strip():
        rows.append(json.loads(line))

parsed = []
for r in rows:
    aid = clean(r.get('action_id'))
    m = ID_RE.match(aid)
    if not m:
        continue
    zone = 'summary' if m.group(1) else 'detail'
    family = m.group(2)
    boss_event_id = int(m.group(3))
    selection_index = int(m.group(4))
    outer = r.get('event_id')
    period = 'first_half' if HALF_RE.search(' '.join(clean(r.get(k)) for k in ('participant_name', 'section_title', 'row_text'))) else 'full_game_or_unspecified'
    parsed.append({
        **r,
        'boss_zone': zone,
        'boss_family': family,
        'boss_event_id': boss_event_id,
        'boss_selection_index': selection_index,
        'outer_event_id_matches_boss': str(outer) == str(boss_event_id),
        'period_class': period,
        'parsed_line': parse_market_line(family, r.get('action_text')),
    })

# Deduplicate repeated whole-zone captures. The BOSS id is the binding authority.
uniq = {}
for r in parsed:
    key = (
        r['boss_zone'], r['boss_family'], r['boss_event_id'], r['boss_selection_index'],
        clean(r.get('participant_name')), clean(r.get('action_text')),
        clean(r.get('section_title')), r['period_class'],
    )
    uniq.setdefault(key, r)
unique = list(uniq.values())

events = defaultdict(lambda: defaultdict(list))
for r in unique:
    events[r['boss_event_id']][r['boss_family']].append(r)

complete_ml = []
for eid, fams in sorted(events.items()):
    ml = [r for r in fams.get('ML', []) if r['boss_zone'] == 'detail' and r['period_class'] == 'full_game_or_unspecified']
    indices = {r['boss_selection_index'] for r in ml}
    if {1, 2, 3}.issubset(indices):
        picks = {i: next(r for r in ml if r['boss_selection_index'] == i) for i in (1, 2, 3)}
        complete_ml.append({
            'boss_event_id': eid,
            'home_like': {'participant': picks[1].get('participant_name'), 'price_text': picks[1].get('action_text'), 'action_id': picks[1].get('action_id')},
            'away_like': {'participant': picks[2].get('participant_name'), 'price_text': picks[2].get('action_text'), 'action_id': picks[2].get('action_id')},
            'draw': {'participant': picks[3].get('participant_name'), 'price_text': picks[3].get('action_text'), 'action_id': picks[3].get('action_id')},
        })

line_dist = defaultdict(Counter)
for r in unique:
    if r['boss_family'] not in {'PS', 'TT'} or r['parsed_line'] is None:
        continue
    line_dist[(r['boss_family'], r['period_class'])][str(r['parsed_line'])] += 1

same_event_families = []
for eid, fams in sorted(events.items()):
    same_event_families.append({
        'boss_event_id': eid,
        'period_hint': 'first_half' if any(r['period_class'] == 'first_half' for vals in fams.values() for r in vals) else 'full_game_or_unspecified',
        'families': sorted(fams),
        'unique_actions_by_family': {fam: len(vals) for fam, vals in sorted(fams.items())},
    })

mismatch = sum(1 for r in parsed if not r['outer_event_id_matches_boss'])
full_game_boss_ids = sorted({r['boss_event_id'] for r in unique if r['period_class'] == 'full_game_or_unspecified'})
first_half_boss_ids = sorted({r['boss_event_id'] for r in unique if r['period_class'] == 'first_half'})
result = {
    'source_snapshot': 'front1_football_contract_inventory_v2 / run 31543824613',
    'binding_rule': 'For BOSS market controls matching (SZ)?(ML|PS|TT)_<event_id>_<selection>, the embedded event_id is authoritative. Outer snapshot labels are capture-container metadata only.',
    'raw_rows': len(rows),
    'parsed_market_rows': len(parsed),
    'unique_market_signatures': len(unique),
    'unique_boss_event_ids': len(events),
    'full_game_or_unspecified_boss_event_ids': full_game_boss_ids,
    'first_half_boss_event_ids': first_half_boss_ids,
    'outer_event_id_mismatch_rows': mismatch,
    'outer_event_id_mismatch_rate': mismatch / len(parsed) if parsed else None,
    'unique_event_ids_by_family': {fam: sorted({r['boss_event_id'] for r in unique if r['boss_family'] == fam}) for fam in ('ML', 'PS', 'TT')},
    'complete_full_game_ml_1_2_3_events': complete_ml,
    'complete_full_game_ml_event_count': len(complete_ml),
    'same_event_family_inventory': same_event_families,
    'line_distribution': {f'{fam}|{period}': dict(sorted(cnt.items(), key=lambda x: float(x[0]))) for (fam, period), cnt in sorted(line_dist.items())},
    'more_control_raw_count': sum(1 for r in rows if clean(r.get('action_text')).casefold() in {'más', 'mas', 'more'}),
    'guard': 'Offline identity correction only. PS line parsing recognizes unicode quarter/half/three-quarter tokens before the American price. ML prices are intentionally excluded from line_distribution. This does not refresh prices, establish current availability, infer Double Chance from +0.5, infer team totals from TT, or score any hypothesis.',
}
OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k: result[k] for k in (
    'raw_rows', 'parsed_market_rows', 'unique_market_signatures', 'unique_boss_event_ids',
    'full_game_or_unspecified_boss_event_ids', 'first_half_boss_event_ids',
    'outer_event_id_mismatch_rows', 'outer_event_id_mismatch_rate',
    'complete_full_game_ml_event_count', 'line_distribution', 'more_control_raw_count'
)}, indent=2, ensure_ascii=False))
