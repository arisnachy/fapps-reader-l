# KIRA Ω — EURO19 BROAD OPPONENT TEAM TOTAL UNDER 3.5 V1

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / OUTCOMES UNOPENED

## Purpose
Test a broad football market-translation family that can select different events from the existing +1.5 families and materially increase daily coverage.

## Frozen population
Football-Data leagues:
`E0,E1,E2,E3,SP1,SP2,D1,D2,I1,I2,F1,F2,N1,P1,SC0,SC1,SC2,SC3,B1`.

Use closing market-average `AvgCH,AvgCD,AvgCA`; all sources/required columns must pass.

## Frozen pregame selector
For every match:
- normalize H/D/A implied probabilities;
- compare HOME vs AWAY only and select the uniquely higher-probability participant;
- require selected participant no-vig probability >=0.50;
- wager contract is **OPPONENT team total UNDER 3.5 goals**;
- all eligible events enter date pool;
- max THREE distinct events/date;
- rank by higher selected-participant probability, then lower selected-side price, league/home/away/side lexical order;
- one event creates max one leg;
- no target score/result used for candidate creation or ranking.

This is not a retune of the old core OPP-TT experiment; it is a new broad event selector frozen before target outcomes are scored.

## Settlement
WIN if the opponent of the selected participant scores 0,1,2 or 3 full-match goals; LOSS if opponent scores >=4. No line widening, no full-game total substitution, no selected-team total, no +1.5 wrapper.

## Sequential validation
- DEV season `2223`.
- independent OOS season `2324`, unopened unless DEV passes.

## User Gate90
Each block:
- >=500 selected legs;
- >=180 candidate dates;
- observed leg survival >90%;
- observed whole daily-bundle survival >90%;
- all 19 sources PASS;
- outcome-blind generation, event uniqueness, max3/date and settlement completeness PASS.

Wilson95 intervals are reported diagnostically, not vetoes under User Gate90.

Failure closes V1 without threshold or line rescue.

## Mission accounting
After terminal OOS PASS, reconstruct 2025 outcome-blind and add only football events not already present in Tier-B + Global Football + Euro9 + Lower10. Same-event wrappers never manufacture extra CORE legs.

Production remains zero until Juancito exposes the exact opponent-team-total U3.5 family/line on the current event, with fresh price and settlement binding.
