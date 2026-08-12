# KIRA Ω — EURO19 OPPONENT TT U3.5 — MARGINAL P50-55 V1

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / TARGET BLOCKS UNSCORED

## Purpose
Create event-disjoint coverage relative to all p>=0.55 selected-favorite +1.5 families while retaining the independently validated opponent-team-total U3.5 thesis.

## Population
Football-Data leagues:
`E0,E1,E2,E3,SP1,SP2,D1,D2,I1,I2,F1,F2,N1,P1,SC0,SC1,SC2,SC3,B1`.
Required `Date,HomeTeam,AwayTeam,AvgCH,AvgCD,AvgCA,FTHG,FTAG`; every source must pass.

## Frozen selector
- normalize closing market-average H/D/A implied probabilities;
- choose unique higher-probability HOME/AWAY participant;
- require **0.50 <= selected no-vig probability < 0.55**;
- contract = OPPONENT TEAM TOTAL UNDER 3.5 full match;
- max THREE distinct events/date;
- rank probability desc, selected-side price asc, league/home/away/side lexical;
- one event one leg;
- target result does not create/remove/rank candidates.

The `<0.55` boundary is structural disjointness from admitted p>=0.55 families, not outcome tuning.

## Sequential validation
- DEV season `2021` (2020-21).
- OOS season `2122` (2021-22), unopened unless DEV passes.

## User Gate90
Each block:
- all 19 sources PASS;
- >=300 selected legs;
- >=150 candidate dates;
- observed leg survival >90%;
- observed daily-bundle survival >90%;
- outcome-blind generation, event uniqueness, max3/date and settlement completeness PASS.

Wilson95 intervals are diagnostics only. Any failure closes V1 with no threshold/season/line rescue.

## Coverage/production
Terminal OOS PASS alone permits outcome-blind 2025 reconstruction and literal event dedupe. Production still requires exact fresh Juancito opponent Team Total U3.5 availability, price, accumulator compatibility and settlement binding.
