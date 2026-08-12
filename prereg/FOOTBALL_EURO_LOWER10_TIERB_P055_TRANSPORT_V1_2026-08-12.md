# KIRA Ω — EURO LOWER10 +1.5 MULTI3 — TIER-B P055 TRANSPORT V1

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / OUTCOMES UNOPENED

## Purpose

Test whether the already-frozen Tier-B P055 selected-favorite +1.5 rule transports unchanged into major European lower divisions, creating winter calendar coverage without tuning to their outcomes.

## Frozen rule — exact inheritance / NO RETUNE

- closing market-average H/D/A columns `AvgCH, AvgCD, AvgCA` only;
- normalized no-vig probabilities;
- select uniquely higher-probability HOME or AWAY participant;
- selected favorite probability >= 0.55;
- exact settlement: selected participant +1.5 goals, full match;
- all eligible games enter the date pool; max 3 distinct events/date globally within this family;
- ranking: higher no-vig favorite probability, lower selected-side price, lexical league/home/away/side;
- one event = max one leg;
- target outcome cannot create/remove/rank candidates.

## Frozen population

Football-Data codes:
`E1, E2, E3, SP2, D2, I2, F2, SC1, SC2, SC3`.

These represent English Championship/League One/League Two, Spanish Segunda, German 2. Bundesliga, Italian Serie B, French Ligue 2, and Scottish Championship/League One/League Two.

Any source missing required columns fails closed; no bookmaker-column substitution.

## Sequential sealed validation

- DEV: season `2223`.
- independent OOS: season `2324`.
- OOS MUST remain unopened unless DEV passes all gates.

## Gate V2 >90%

Each block independently requires:
- selected legs >= 300;
- candidate dates >= 150;
- leg observed survival >90%;
- leg Wilson95 LCB >90%;
- daily bundle observed survival >90%;
- daily bundle Wilson95 LCB >90%;
- source completeness, outcome-blind generation, one-event-one-leg, max3/date and complete settlement PASS.

Any failure closes V1. No threshold/line/ranking/source rescue.

## Mission use

Only terminal independent OOS PASS authorizes an outcome-blind 2024-12-27..2025-12-17 calendar reconstruction. Production remains contingent on exact fresh Juancito selected-team +1.5 availability and operator settlement on each event.
