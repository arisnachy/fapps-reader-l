# KIRA Ω — EURO19 OPPONENT TT U3.5 — MARGINAL P45-50 V1

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / TARGET BLOCKS UNSCORED

Purpose: test a football event band structurally disjoint from every admitted p>=0.50 family, to fill red weekdays rather than stack more legs onto already-green matchdays.

Population: Football-Data `E0,E1,E2,E3,SP1,SP2,D1,D2,I1,I2,F1,F2,N1,P1,SC0,SC1,SC2,SC3,B1` using `Date,HomeTeam,AwayTeam,AvgCH,AvgCD,AvgCA,FTHG,FTAG`. All 19 sources must pass; no column/source substitution.

Frozen selector:
- normalize closing AvgCH/AvgCD/AvgCA implied probabilities;
- choose unique higher-probability HOME/AWAY participant;
- require **0.45 <= selected no-vig probability < 0.50**;
- wager OPPONENT TEAM TOTAL UNDER 3.5 full match;
- max THREE distinct events/date;
- rank probability desc, selected-side price asc, league/home/away/side lexical;
- target result cannot create/remove/rank candidates; one event max one leg.

Settlement: WIN iff opponent scores <=3, LOSS iff opponent scores >=4. No line/wrapper substitution.

Sequential validation:
- DEV season `1819`;
- OOS season `1920`, unopened unless DEV passes.

User Gate90 each block: all 19 sources PASS, >=300 selected legs, >=150 candidate dates, observed leg survival >90%, observed daily-bundle survival >90%, outcome-blind generation, unique events, max3/date, complete settlement. Wilson95 is diagnostic only.

Any failure closes V1 without threshold/season/line rescue. Terminal OOS PASS permits outcome-blind 2025 reconstruction and literal cross-family event dedupe. Production still requires exact Juancito opponent Team Total U3.5 availability, price, freshness, accumulator compatibility and settlement binding.
