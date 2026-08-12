# KIRA Ω — SUMMER16 OPPONENT TT U3.5 — MARGINAL P50-55 V1

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / TARGET BLOCKS UNSCORED

## Mission-specific purpose
The existing Summer16 Tier-B +1.5 family selects market favorites with no-vig probability >=0.55. The broad Summer16 U3.5 family is scientifically strong but overlaps heavily because it ranks the same strongest events first. This experiment tests a disjoint pregame band so any eventual 2025 legs are new events by construction.

## Frozen population/source
Country files:
`ARG,AUT,BRA,CHN,DNK,FIN,IRL,JPN,MEX,NOR,POL,ROU,RUS,SWE,SWZ,USA`.
Required columns `Date,Home,Away,League,AvgCH,AvgCD,AvgCA,HG,AG`; fail closed if any target-year source is missing.

## Frozen selector
For each match:
- normalize AvgCH/AvgCD/AvgCA implied probabilities;
- choose unique higher-probability HOME/AWAY participant;
- require **0.50 <= selected no-vig probability < 0.55**;
- contract: OPPONENT TEAM TOTAL UNDER 3.5 full match;
- retain max THREE distinct events/date;
- rank probability desc, selected-side price asc, source/league/home/away/side lexical;
- target score cannot create/remove/rank candidates.

The upper bound `<0.55` is frozen for structural disjointness from Tier-B, not selected from target outcomes.

## Settlement
WIN iff opponent scores <=3; LOSS iff opponent scores >=4. No line or wrapper substitution.

## Sequential independent blocks
- DEV calendar year 2015.
- OOS calendar year 2016, unopened unless DEV PASS.

## User Gate90
Each block:
- all 16 source gates PASS;
- >=250 selected legs;
- >=120 candidate dates;
- observed leg survival >90%;
- observed daily-bundle survival >90%;
- outcome-blind selector, unique events, max3/date and complete settlement PASS.

Wilson95 intervals are diagnostics only. Any failure closes V1; no threshold/year/line rescue.

## Coverage accounting
Only terminal OOS PASS authorizes an outcome-blind 2025 reconstruction. Since the selector is `<0.55`, it is event-disjoint from the p>=0.55 Tier-B family within the same source universe; normal cross-family literal date+home+away dedupe still applies against every other admitted family.

Production remains contingent on exact current Juancito opponent Team Total U3.5 market availability/price/freshness/accumulator/settlement.
