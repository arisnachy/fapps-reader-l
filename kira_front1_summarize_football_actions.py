from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

SRC = Path('front1_football_contract_inventory_v2/football_market_actions.jsonl')
OUT = Path('front1_football_contract_inventory_v2/actions_summary.json')

TERMS = {
    'double_chance': re.compile(r'(?i)double\s+chance|doble\s+oportunidad|(^|\s)(1x|x2|12)(\s|$)'),
    'draw_no_bet': re.compile(r'(?i)draw\s+no\s+bet|empate\s+(?:no\s+)?apuesta|sin\s+empate|\bdnb\b'),
    'team_total': re.compile(r'(?i)team\s+total|total\s+(?:del|por|solo\s+por)\s+equipo'),
    'winning_margin': re.compile(r'(?i)winning\s+margin|margen\s+de\s+victoria'),
    'handicap': re.compile(r'(?i)handicap|hándicap|spread'),
    'moneyline': re.compile(r'(?i)money\s*line|línea\s+de\s+dinero|linea\s+de\s+dinero'),
    'total': re.compile(r'(?i)\btotal\b|over|under|más de|menos de'),
}

def clean(v):
    return re.sub(r'\s+', ' ', str(v or '')).strip()

def id_prefix(action_id: str) -> str:
    s = clean(action_id)
    if not s:
        return '(blank)'
    m = re.match(r'^([A-Za-z]+)', s)
    return m.group(1) if m else s.split('_', 1)[0]

def compact(row):
    keys = ['event_id','source_league','section_title','participant_name','action_text','action_id','row_text','title','aria_label','actionable','locked']
    return {k: row.get(k) for k in keys}

rows=[]
for line in SRC.read_text(encoding='utf-8').splitlines():
    if line.strip():
        rows.append(json.loads(line))

sections=Counter(clean(r.get('section_title')) or '(blank)' for r in rows)
prefixes=Counter(id_prefix(r.get('action_id')) for r in rows)
action_texts=Counter(clean(r.get('action_text')) or '(blank)' for r in rows)
participants=Counter(clean(r.get('participant_name')) or '(blank)' for r in rows)
by_event=Counter(str(r.get('event_id') or '(blank)') for r in rows)
actionable_sections=Counter(clean(r.get('section_title')) or '(blank)' for r in rows if r.get('actionable') is True)
actionable_prefixes=Counter(id_prefix(r.get('action_id')) for r in rows if r.get('actionable') is True)

examples_by_section=defaultdict(list)
examples_by_prefix=defaultdict(list)
term_examples={k:[] for k in TERMS}
for r in rows:
    sec=clean(r.get('section_title')) or '(blank)'
    pre=id_prefix(r.get('action_id'))
    if len(examples_by_section[sec])<4: examples_by_section[sec].append(compact(r))
    if len(examples_by_prefix[pre])<6: examples_by_prefix[pre].append(compact(r))
    corpus=' | '.join(clean(r.get(k)) for k in ('section_title','participant_name','action_text','action_id','row_text','title','aria_label'))
    for name,rx in TERMS.items():
        if rx.search(corpus) and len(term_examples[name])<20:
            term_examples[name].append(compact(r))

# Extra BOSS prefix signatures useful for canonical-family mapping.
prefix_section=defaultdict(Counter)
for r in rows:
    prefix_section[id_prefix(r.get('action_id'))][clean(r.get('section_title')) or '(blank)'] += 1

summary={
    'source_snapshot':'front1_football_contract_inventory_v2 / run 31543824613',
    'rows_total':len(rows),
    'actionable_rows':sum(1 for r in rows if r.get('actionable') is True),
    'locked_rows':sum(1 for r in rows if r.get('locked') is True),
    'event_count':len({str(r.get('event_id')) for r in rows if r.get('event_id') is not None}),
    'section_counts':sections.most_common(),
    'actionable_section_counts':actionable_sections.most_common(),
    'id_prefix_counts':prefixes.most_common(),
    'actionable_id_prefix_counts':actionable_prefixes.most_common(),
    'prefix_to_sections':{k:v.most_common() for k,v in sorted(prefix_section.items())},
    'top_action_texts':action_texts.most_common(80),
    'top_participants':participants.most_common(60),
    'rows_by_event':by_event.most_common(),
    'term_match_counts':{k:sum(1 for r in rows if rx.search(' | '.join(clean(r.get(f)) for f in ('section_title','participant_name','action_text','action_id','row_text','title','aria_label')))) for k,rx in TERMS.items()},
    'term_examples':term_examples,
    'examples_by_section':dict(examples_by_section),
    'examples_by_prefix':dict(examples_by_prefix),
    'guard':'Offline summary of already-persisted public snapshot only. No new market capture, no science scoring, no settlement inference, and missing families remain non-negative evidence because original capture coverage_complete=false.'
}
OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k:summary[k] for k in ('rows_total','actionable_rows','locked_rows','event_count','section_counts','id_prefix_counts','term_match_counts')}, indent=2, ensure_ascii=False))
