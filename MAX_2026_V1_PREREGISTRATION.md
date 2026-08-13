# KIRA Ω — MAX 2026 V1 PREREGISTRATION

## Mission
Test whether the practical MAX concept can be promoted to the pinned daily strategy by demonstrating both availability and complete-ticket survival on the settled 2026 calendar through 2026-08-12.

## Frozen universe
Use every domestic league/division with historical 1X2 odds and full-time scores retrievable from Football-Data.co.uk in either:
1. MAIN 2025/26 and, if available, 2026/27 season CSVs for the 22 standard divisions: E0,E1,E2,E3,E4,SC0,SC1,SC2,SC3,D1,D2,I1,I2,SP1,SP2,F1,F2,N1,B1,P1,T1,G1.
2. EXTRA country CSVs: ARG,AUT,BRA,CHN,DNK,FIN,IRL,JPN,MEX,NOR,POL,ROU,RUS,SWE,SWZ,USA.

No competition, source, date, team, failure or success may be removed after scoring. Cup/continental competitions are NOT silently inherited; if this domestic-universe test misses availability, cups require a separately preregistered expansion.

## Frozen selector
- Calendar: 2026-01-01 through 2026-08-12 inclusive.
- Prematch market: market-average closing 1X2 where AvgCH/AvgCD/AvgCA are available; otherwise market-average prematch AvgH/AvgD/AvgA.
- Convert H/D/A decimal odds to normalized no-vig probabilities.
- Select the stronger of HOME/AWAY iff `p_favorite_novig >= 0.60`.
- Exact settlement target: selected participant +1.5, full game / regulation settlement corresponding to the source's full-time result.
- Exact distinct event identity = date + source + division + home + away.
- Daily deterministic ranking: descending p_favorite_novig; then selected 1X2 price ascending; then source/division/home/away and HOME before AWAY.
- Freeze ranks 1..5 before joining outcomes.
- Ticket T3 = ranks 1..3; T4 = ranks 1..4; T5 = ranks 1..5. No substitutes after a leg loses.

## Outcome isolation
Candidate eligibility/ranking MUST NOT read full-time score columns. Full-time outcomes are stored separately and joined only after the ranked pre-settlement ledger is written and hashed.

## Frozen gates
Calendar denominator is every date from 2026-01-01 through 2026-08-12, including dates with zero eligible events.

Availability:
- CORE3 daily availability = days with >=3 eligible / all 224 calendar days.
- FULL_STACK daily availability = days with >=5 eligible / all 224 calendar days.
- `DAILY_AVAILABILITY_PASS` requires FULL_STACK = 224/224 (100%). This is deliberately strict because the proposed pinned output is three daily tickets T3/T4/T5.

Certainty, evaluated only on dates where each N exists:
- observed complete-ticket survival > 0.90;
- Wilson95 lower confidence bound >= 0.90;
- at least 35 evaluable dates.
Each of T3/T4/T5 is reported separately.

Pinned-strategy PASS requires simultaneously:
1. source/integrity gates pass;
2. candidate_generation_used_outcomes=false;
3. duplicate_event_keys=0;
4. DAILY_AVAILABILITY_PASS;
5. T3, T4 and T5 each pass the complete-ticket certainty gate.

If any condition fails, decision is `NO_PASS_DO_NOT_PIN`. No threshold retune, source pruning, date exclusion or line change is authorized in this run.
