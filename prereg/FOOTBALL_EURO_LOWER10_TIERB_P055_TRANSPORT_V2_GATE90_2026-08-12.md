# KIRA Ω — EURO LOWER10 TIER-B P055 TRANSPORT V2 — USER GATE90

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / OOS 2324 UNOPENED

## Why V2 exists

V1 used the unchanged Tier-B P055 +1.5 selector and produced DEV 2223 observed survival above 90%, but its preregistration additionally required Wilson95 LCB >90% and >=150 candidate dates. Those extra vetoes are stricter than the user's explicit operational directive: **if observed performance is above 90%, PASS**.

V1 remains terminal `NO_PASS` under its own preregistration and is not rewritten.

This V2 is frozen prospectively before the untouched 2324 block is requested/scored. It changes **only the decision gate**, not the sports selector, line, ranking, sources or settlement.

## Immutable sports rule

Exactly V1:
- leagues `E1,E2,E3,SP2,D2,I2,F2,SC1,SC2,SC3`;
- closing `AvgCH, AvgCD, AvgCA`;
- normalized no-vig favorite;
- favorite probability >=0.55;
- selected favorite +1.5 goals full match;
- max 3 distinct events/date;
- same deterministic ranking;
- no target outcome in selection.

## Independent OOS block

- season `2324` only;
- must fetch all ten sources successfully with required columns;
- one event one leg; max3/date; complete settlement;
- no threshold/line/ranking/source change after this freeze.

## User Gate90 decision

Terminal `OPERATIONAL_OOS_PASS` requires ALL:
- source/completeness/firewall/uniqueness gates PASS;
- selected legs >=200;
- candidate dates >=100;
- observed leg survival >90.00%;
- observed daily-bundle survival >90.00%.

Wilson95 intervals remain mandatory diagnostics and are reported, but are **not a veto** under User Gate90 V2.

Any observed-rate failure closes V2. No rescue retune.

## Production boundary

OOS PASS permits an outcome-blind 2025 common-window coverage reconstruction only. Live use still requires exact current Juancito participant +1.5 full-game availability, quote freshness and package/correlation gates.
