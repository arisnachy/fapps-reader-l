# KIRA Ω — EURO9 FAVORITE +1.5 MULTI3 — TIER-B P055 TRANSPORT V1

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / VALIDATION OUTCOMES UNOPENED

## Question

Does the already-frozen Tier-B Extra16 rule transport unchanged into nine major European Football-Data leagues, creating winter multi-event coverage without tuning the selector to European outcomes?

## Frozen inheritance — NO RETUNE

This transport inherits the Tier-B sports rule unchanged:

- prematch/closing market-average H/D/A only;
- convert H/D/A decimal odds to normalized no-vig probabilities;
- select the uniquely higher-probability HOME or AWAY participant;
- require selected favorite no-vig probability >= 0.55;
- exact contract = selected participant +1.5 goals, full match;
- max THREE distinct events per calendar date globally;
- ranking = higher selected-favorite no-vig probability, then lower selected-side decimal price, then lexical league/home/away/side;
- one event can create at most one leg;
- no target score/outcome can create, remove or rank a candidate.

No p-threshold, line, side, date cap or ranking field was chosen from Euro9 outcomes.

## Frozen Euro9 population

Football-Data league codes:
`E0, SP1, D1, I1, F1, N1, P1, SC0, B1`.

Use season CSVs and the closing average columns `AvgCH`, `AvgCD`, `AvgCA` plus `Date`, `HomeTeam`, `AwayTeam`, `FTHG`, `FTAG`. A league/season missing required columns is a source-gate failure; do not silently substitute bookmaker columns.

## Validation blocks

Sequential and sealed:

- DEV: season `2223` for all Euro9 leagues.
- independent OOS: season `2324` for all Euro9 leagues.

OOS must not be requested/scored if DEV fails.

## Settlement

Selected participant +1.5 is WIN unless the selected participant loses by 2+ goals after the official full-match settlement scope; target exact historical settlement is:
`selected_goal_diff + 1.5 > 0`.

No +0.5/+2.5, Double Chance, ML, DNB, total, halftime or Asian quarter-ball substitution.

## Gate V2 >90%

Each block independently requires:
- selected legs >= 300;
- candidate dates >= 150;
- leg observed survival >90%;
- leg Wilson95 LCB >90%;
- whole daily bundle observed survival >90%;
- whole daily bundle Wilson95 LCB >90%;
- source identity/completeness, temporal firewall, event uniqueness and max3/date audits PASS.

The later block remains sealed if DEV fails. Any failure closes this V1; no rescue retune.

## Mission use

Only after terminal OOS PASS may the unchanged rule be reconstructed outcome-blind on the 2024-12-27..2025-12-17 common window and literally deduped against existing Tier-B/T3/Global-Football events. Production still requires fresh exact Juancito event + same selected participant +1.5, full-game settlement, actionable quote and freshness.
