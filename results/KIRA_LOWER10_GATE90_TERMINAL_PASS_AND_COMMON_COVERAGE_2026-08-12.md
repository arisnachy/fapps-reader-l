# KIRA Ω — LOWER10 GATE90 TERMINAL PASS + COMMON-WINDOW IMPACT

Date: 2026-08-12 America/Santo_Domingo

## Prospective Gate90 OOS

V1 DEV 2223 used the unchanged Tier-B P055 selected-favorite +1.5 selector on `E1,E2,E3,SP2,D2,I2,F2,SC1,SC2,SC3` and produced observed rates >90%, but its own stricter Wilson/date preregistration remained NO_PASS. V1 was not rewritten.

Before the untouched 2324 block was opened, V2 User Gate90 was frozen at commit `c92419901ed86c3a34fa3f836c2815fb433e481f`, changing only the decision rule, not selector, line, sources or ranking.

V2 OOS run: `31628073693`; artifact `9153916322`; digest `sha256:b4b51c0f4adfe042b0bdf22389dba0b887e6f1fb2b09928f582a6971535aaf91`.

OOS 2324:
- selected legs: **317**;
- leg wins: **306/317 = 96.52997%**;
- leg Wilson95 LCB: **93.89419%**;
- candidate dates: **151**;
- daily bundles: **142/151 = 94.03974%**;
- bundle Wilson95 LCB: **89.06138%** (diagnostic, not Gate90 veto);
- multiplicity: 54 x1, 28 x2, 69 x3;
- duplicate event keys: 0;
- source gate: PASS for all 10 leagues;
- outcome-blind candidate generation: PASS;
- max3/date: PASS;
- settlement complete: PASS.

User Gate90 terminal decision: **`OPERATIONAL_OOS_PASS`**.

## Outcome-blind 2025 common-window reconstruction

Run `31628501608`; artifact `9154079874`; digest `sha256:1fc6849475eb257ca4fa2a198934c9b3421b0995b1b00308705c197c67b13ca2`.

Window: `2024-12-27..2025-12-17` = 356 days.

The common-window script requests only `Date, HomeTeam, AwayTeam, AvgCH, AvgCD, AvgCA`; it does not request/load result columns.

Lower10 output:
- eligible pre-cap: **615**;
- selected legs: **336**;
- candidate dates: **157**;
- multiplicity: 52 x1, 31 x2, 74 x3;
- outcome columns requested: false;
- outcomes loaded: false;
- all 20 league-season sources (2425 + 2526) PASS.

## Literal union audit

Existing frozen science-qualified Gate90 baseline before Lower10:
- Tier-B + T3 = 157/356 CORE>=3, 199 red, 451 missing slots;
- + Global Football = 162/356, 194 red, 428 missing;
- + Euro9 P055 = **192/356, 164 red, 364 missing**.

Cross-route football identity is literal `date + Home + Away`; Tennis T3 remains sport-distinct. The authoritative T3 ledger is 115 events / 88 dates, including United Cup 2024-12-29 and 2024-12-30.

Lower10 overlap against Tier-B + Global Football + Euro9:
- selected Lower10 events: 336;
- already represented football events: **0**;
- new distinct football events: **336**.

After Lower10:
- **CORE>=3 = 220/356**;
- **red dates = 136**;
- **missing slots to CORE3 = 300**;
- newly green dates vs pre-Lower10 = **+28**;
- missing slots removed = **64**.

Final histogram after Tier-B + T3 + Global Football + Euro9 + Lower10:
- 0: 61 days;
- 1: 42;
- 2: 33;
- 3: 44;
- 4: 41;
- 5: 24;
- 6: 20;
- 7: 18;
- 8: 21;
- 9: 23;
- 10: 21;
- 11: 6;
- 12: 2.

## Remaining monthly deficit

| Month | CORE>=3 | Red | Missing |
|---|---:|---:|---:|
| 2024-12 (5d) | 4 | 1 | 3 |
| 2025-01 | 16 | 15 | 28 |
| 2025-02 | 25 | 3 | 6 |
| 2025-03 | 17 | 14 | 32 |
| 2025-04 | 28 | 2 | 3 |
| 2025-05 | 20 | 11 | 22 |
| 2025-06 | 13 | 17 | 42 |
| 2025-07 | 14 | 17 | 38 |
| 2025-08 | 21 | 10 | 20 |
| 2025-09 | 16 | 14 | 35 |
| 2025-10 | 21 | 10 | 25 |
| 2025-11 | 14 | 16 | 37 |
| 2025-12 (17d) | 11 | 6 | 9 |

The largest unresolved seasonal hole is still June-July; more winter football alone cannot close the mission.

## Production boundary

This is science-qualified historical candidate coverage under User Gate90. Live production still requires the exact current Juancito event, selected participant +1.5 full-game market, current quote/freshness, one-event-one-leg dedupe, package correlation gates and current inventory certification.
