# KIRA Ω — MAX 2026 V2 UNIVERSAL — PREREGISTRATION

## Mission
Test the practical MAX strategy on every settled calendar day from 2026-01-01 through 2026-08-12 using the broad daily football universe, then decide whether it is strong enough to pin as the 3/4/5 daily strategy.

## Frozen source/universe
For each calendar date D, use the OddsPortal exact-date football archive page resolved from:
`https://www.oddsportal.com/matches/football/YYYYMMDD/` (currently redirects to `/football/YYYY-MM-DD/`).

Universe = every football event actually exposed on that date page after expanding all `SHOW MORE` controls, across countries, leagues, cups, continental competitions, women/youth/reserve competitions and other football competitions. No country, competition, team, date, failure or success may be removed after scoring.

The row-level displayed 1-X-2 odds are treated as the archived pre-match odds snapshot supplied by the source. Rows without all three numeric 1-X-2 prices cannot become candidates.

## Frozen selector
- Calendar: 2026-01-01 through 2026-08-12 inclusive (224 dates).
- Parse each event's date, competition, HOME/AWAY participants and displayed 1-X-2 decimal prices.
- Normalize implied H/D/A probabilities to no-vig probabilities.
- Strong side must be HOME or AWAY; draws are not selectable.
- Candidate iff selected HOME/AWAY `p_favorite_novig >= 0.60`.
- Exact target contract for science settlement: selected participant +1.5, regulation/full-time 90-minute football result.
- Daily rank: descending p_favorite_novig; then selected 1X2 price ascending; then competition/home/away deterministic lexical tie-breakers.
- Exact-event dedup by date + competition + home + away.
- Freeze ranks 1..5 BEFORE settlement.
- T3 = rank 1..3; T4 = rank 1..4; T5 = rank 1..5. No result-based substitutions.

## Outcome isolation
The source row contains both score and odds. Parser may store scores in a separate outcome dictionary during ingestion, but candidate eligibility/ranking is forbidden from consulting score/status/outcome fields. `candidate_generation_used_outcomes=false` must be emitted. The rank1..5 pre-settlement ledger must be written and SHA256-hashed before the settlement join.

## Settlement
- `Finished`: selected +1.5 survives iff selected regulation goal difference + 1.5 > 0.
- `After ET` or `After Pen.`: regulation was tied before extra time/penalties, therefore any selected participant +1.5 regulation handicap is a WIN.
- Any ranked candidate whose regulation settlement cannot be resolved is `UNRESOLVED` and blocks pinning; it may not be silently dropped.

## Frozen gates
Availability denominator = all 224 calendar dates, including dates with zero candidates.
- CORE3 availability = dates with >=3 candidates / 224.
- FULL_STACK availability = dates with >=5 candidates / 224.
- `DAILY_AVAILABILITY_PASS` requires FULL_STACK = 224/224 (100%), because the proposed pinned output is T3+T4+T5 every day.

Certainty for each T3/T4/T5, evaluated on dates where that ticket exists:
- >=35 evaluable dates;
- observed complete-ticket survival > 0.90;
- Wilson95 lower confidence bound >= 0.90.

`PIN_MAX_2026_V2_PASS` requires simultaneously:
1. all 224 date pages fetched/parsed without an unresolved source hole;
2. candidate generation did not use outcomes;
3. zero duplicate exact event keys after deterministic dedup audit;
4. zero unresolved ranked settlements;
5. DAILY_AVAILABILITY_PASS;
6. T3, T4 and T5 each pass the certainty gate.

Otherwise decision is `NO_PASS_DO_NOT_PIN` or `EVIDENCE_INCOMPLETE_DO_NOT_PIN`. No threshold retune, source pruning, date exclusion, competition filtering, line change or post-result repair is authorized in this run.
