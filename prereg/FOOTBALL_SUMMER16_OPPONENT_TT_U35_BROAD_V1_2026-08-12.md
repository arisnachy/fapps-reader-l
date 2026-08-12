# KIRA Ω — SUMMER16 BROAD OPPONENT TEAM TOTAL UNDER 3.5 V1

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / TARGET BLOCKS UNSCORED

## Purpose
Transport the independently strong opponent-team-total U3.5 catastrophe-avoidance thesis into summer-calendar leagues to attack the June-July DAILY CORE deficit with distinct events.

## Frozen population
Football-Data country files:
`ARG,AUT,BRA,CHN,DNK,FIN,IRL,JPN,MEX,NOR,POL,ROU,RUS,SWE,SWZ,USA`.

Required columns:
`Date,Home,Away,League,AvgCH,AvgCD,AvgCA,HG,AG`.
A country file missing required columns or target-year data fails closed; no source or bookmaker-column substitution.

## Frozen pregame selector
For every target-year match:
- normalize closing AvgCH/AvgCD/AvgCA implied probabilities;
- select the unique HOME/AWAY participant with higher no-vig probability;
- require selected participant probability >=0.50;
- contract = OPPONENT team total UNDER 3.5 full-match goals;
- all eligible distinct events enter the date pool;
- retain max THREE events/date globally;
- deterministic ranking: selected probability desc, selected-side price asc, source/league/home/away/side lexical;
- one event = max one leg;
- target HG/AG cannot create, remove or rank candidates.

## Frozen settlement
WIN iff opponent of selected participant scores <=3 full-match goals; LOSS iff opponent scores >=4. No U2.5/U4.5, full-game total, selected-team total or +1.5 wrapper substitution.

## Sequential validation
- DEV calendar year 2017.
- independent OOS calendar year 2018, never scored unless DEV passes.

These blocks are separate from the Euro19 2223/2324 validation and from the 2025 mission window.

## User Gate90
Each block requires:
- all 16 sources PASS with target-year rows;
- >=400 selected legs;
- >=180 candidate dates;
- observed leg survival >90.00%;
- observed whole daily-bundle survival >90.00%;
- outcome-blind selector audit, duplicate event keys zero, max3/date and settlement completeness PASS.

Wilson95 intervals are mandatory diagnostics but not Gate90 vetoes.

Any failure closes V1. No threshold/line/year/source rescue after this freeze.

## Mission accounting
Only terminal OOS PASS authorizes an outcome-blind 2025 reconstruction. Cross-family accounting uses literal football event identity date+home+away, so an event already present in another admitted family contributes zero extra CORE legs.

Production remains conditional on exact current Juancito opponent-team-total U3.5 availability, price, freshness, accumulator compatibility and settlement binding.
