# KIRA Ω — MAX-N EXTRA16 FAVORITE +1.5 — 2021 STRESS TEST PREREGISTRATION

**Frozen before scoring rank-4..rank-7 ticket outcomes.**

## Status
`PREREGISTERED_RETROSPECTIVE_STRESS_TEST`

This is not a new independent OOS block because calendar year 2021 was already used by `FOOTBALL_EXTRA16_FAVORITE_PLUS1_5_MULTI3_V1_2021`. The previous frozen engine retained at most three events/date. This extension measures whether the *same* frozen eligibility and ordering can support larger 4–7-leg complete-date tickets. It must not be promoted to production without independent/prospective confirmation.

## Frozen invariants
- sources exactly: `ARG,AUT,BRA,CHN,DNK,FIN,IRL,JPN,MEX,NOR,POL,ROU,RUS,SWE,SWZ,USA`;
- calendar year exactly 2021;
- closing market-average H/D/A fields exactly `AvgCH/AvgCD/AvgCA`;
- compute no-vig HOME/AWAY probabilities exactly as the existing MULTI3 runner;
- eligible market favorite iff `p_favorite_novig >= 0.60`;
- selected contract: exact selected participant full-game `+1.5`;
- event identity exactly date/source/league/home/away;
- same deterministic ordering as existing MULTI3: `(-p_favorite_novig, selected_price, source, league, Home, Away, HOME-before-AWAY)`;
- no result/outcome field may influence eligibility, ranking, N, source inclusion or ticket composition;
- no country/source may be removed after settlement;
- failures must be preserved.

## Only permitted change from MULTI3
The old scientific selector used `MAX3=3`. This stress test first freezes the full ordered candidate list per date, then evaluates prefixes `N = 3,4,5,6,7`. No threshold, source, line, ranking or settlement rule changes.

## Ticket definition
For each N, a date is evaluable only when it has at least N frozen eligible distinct events. The N-leg ticket is exactly ranks 1..N. It survives iff every selected participant +1.5 leg survives (`selected_goal_diff + 1.5 > 0`).

## Metrics frozen before settlement
For each N=3..7 report:
- evaluable dates;
- ticket wins / losses;
- observed complete-ticket survival;
- Wilson 95% LCB/UCB;
- total selected legs;
- leg wins/losses for the prefix universe;
- every failed date and failed event;
- source/team/month concentration;
- overlap/nesting across N.

## Interpretation gates
- `OBSERVED_FLOOR`: complete-ticket survival > 0.90;
- `TARGET`: complete-ticket survival > 0.92;
- `STRONG_WILSON_SIGNAL`: Wilson95 LCB >= 0.90;
- evidence is `TOO_THIN` when evaluable dates < 35, regardless of observed rate.

These are stress-test interpretation gates and do not alter or replace the original MULTI3 production science gate (`dates>=200 && Wilson95 LCB>=0.92`).

## Decision rule
Choose the largest N with `evaluable_dates >= 35`, observed survival >0.90 and Wilson95 LCB >=0.90 as the **MAX-N historical stress-test winner**. If no N>=4 satisfies that, retain N=3. This winner remains `RETROSPECTIVE_ONLY` until an independent or prospective block confirms it.
