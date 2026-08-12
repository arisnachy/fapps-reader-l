# KIRA Ω — EURO9 TIER-B P055 TRANSPORT + COMMON-WINDOW IMPACT

Date: 2026-08-12 America/Santo_Domingo

## Terminal science decision

Hypothesis: `FOOTBALL_EURO9_FAVORITE_PLUS1_5_MULTI3_TIERB_P055_TRANSPORT_V1`.

Frozen unchanged transport from Extra16 Tier-B:
- Euro9 leagues: `E0, SP1, D1, I1, F1, N1, P1, SC0, B1`;
- closing market-average no-vig favorite probability `>=0.55`;
- selected favorite participant `+1.5` goals, full match;
- global max 3 distinct events/date;
- deterministic pregame ranking;
- no target outcome used for candidate generation.

Preregistration commit: `8b70618361ce35831a8b11fd928637ed8e60650d`.

The first DEV execution exposed only a classification-code boolean inversion: `candidate_generation_used_outcomes=False` was incorrectly included directly in Python `all(gates.values())`. The erratum was frozen before OOS at commit `097d6473c9e600212a8bb6be0e8d235535df4c6d`, allowing only the semantic inversion of this audit condition and requiring exact DEV-ledger reproduction before OOS could open.

Ledger-locked gatefix run: `31626628904`; artifact `9153358656`; digest `sha256:20bcc12825780b4d2b3726aa543b83dcd3a96bc3488d871d6d876c25e6c7cc08`.

### DEV 2223 — exact reproduction PASS

- selected ledger SHA256: `f17e823ce6bd039eb6bec116075065f9eaeb064b8ebceae203ea42a99ba83daf` — exact match to the pre-erratum frozen ledger;
- selected legs: 438;
- leg wins: **428/438 = 97.7169%**;
- leg Wilson95 LCB: **95.8488%**;
- candidate dates: 182;
- daily bundles: **172/182 = 94.5055%**;
- bundle Wilson95 LCB: **90.1826%**;
- all substantive gates PASS;
- candidate generation outcome-blind = true.

Only after this exact reproduction did the gatefix runner open OOS 2324.

### Independent OOS 2324 — PASS

- selected ledger SHA256: `87942f5f1263ab9c3949fb0343a0826ba7fcc2398db1d82773ab4efcafd9bc28`;
- selected legs: 450;
- leg wins: **447/450 = 99.3333%**;
- leg Wilson95 LCB: **98.0585%**;
- candidate dates: 185;
- daily bundles: **182/185 = 98.3784%**;
- bundle Wilson95 LCB: **95.3415%**;
- date multiplicity: 39 x1, 27 x2, **119 x3**;
- all substantive Gate-V2 (>90%) checks PASS.

**Terminal decision: `OOS_TRANSPORT_PASS`.** No selector, threshold, line, cap or ranking retune was used between DEV and OOS.

## Outcome-blind common-window reconstruction

Common calendar: `2024-12-27..2025-12-17` = 356 days.

Reconstruction run: `31627042726`; artifact `9153514156`; digest `sha256:27636a8208093e1a4cf7062702e41c008abbca5d255a0ed6ce32f23835848f42`.

The reconstruction requests only:
`Date, HomeTeam, AwayTeam, AvgCH, AvgCD, AvgCA`.

It does **not** request/load score/outcome columns.

Euro9 common-window output:
- 389 selected legs;
- 164 candidate dates;
- multiplicity: 39 x1, 25 x2, 100 x3;
- outcomes loaded = false.

## Exact union/dedupe audit

Frozen inputs used for the literal coverage recomputation:
1. Extra16 Tier-B P055 common 2025 = 561 legs / 247 dates;
2. authoritative T3 calendar = 115 events / 88 dates, including the two manually resolved United Cup dates 2024-12-29 and 2024-12-30;
3. Gate90 Global Football = frozen 252-row pre-settlement ledger;
4. Euro9 P055 = frozen outcome-blind 389-row common-window ledger.

Football event identity for cross-route dedupe is literal `date + Home + Away`; Tennis remains sport-distinct. No same football match can manufacture multiple CORE legs merely because several selectors picked it.

Arithmetic control reproduced the existing checkpoints exactly before admitting Euro9:
- Tier-B + T3 = **157/356 CORE>=3, 199 red, 451 missing slots**;
- adding Global Football = **162/356 CORE>=3, 194 red, 428 missing slots**.

Euro9 overlap against already-admitted Tier-B + Global Football:
- Euro9 selected events: 389;
- already represented football events: 136;
- **new distinct football events: 253**.

After adding Euro9 with literal event dedupe:
- **CORE>=3 = 192/356**;
- **red dates = 164**;
- **missing slots to CORE3 = 364**;
- net newly green dates vs pre-Euro9 state = **+30**;
- net missing slots removed = **64**.

Final date-leg histogram after Tier-B + T3 + Global Football + Euro9:
- 0 legs: 72 days;
- 1 leg: 56 days;
- 2 legs: 36 days;
- 3 legs: 48 days;
- 4 legs: 36 days;
- 5 legs: 20 days;
- 6 legs: 40 days;
- 7 legs: 34 days;
- 8 legs: 11 days;
- 9 legs: 3 days.

## Monthly remaining deficit after Euro9

| Month | CORE>=3 | Red | Missing slots |
|---|---:|---:|---:|
| 2024-12 (5d) | 3 | 2 | 4 |
| 2025-01 | 13 | 18 | 39 |
| 2025-02 | 21 | 7 | 10 |
| 2025-03 | 12 | 19 | 44 |
| 2025-04 | 24 | 6 | 9 |
| 2025-05 | 20 | 11 | 22 |
| 2025-06 | 13 | 17 | 42 |
| 2025-07 | 14 | 17 | 38 |
| 2025-08 | 20 | 11 | 23 |
| 2025-09 | 14 | 16 | 39 |
| 2025-10 | 19 | 12 | 30 |
| 2025-11 | 10 | 20 | 47 |
| 2025-12 (17d) | 9 | 8 | 17 |

Euro9's largest green-date gains were January +9, February +6, 2024-12 +3, 2025-12 +3. It adds zero green days in June-July, confirming that the next coverage attack must be seasonal/complementary rather than another European football variant.

## Production boundary

This is terminal **science-qualified historical candidate coverage**, not final Juancito production coverage. Every live Euro9 leg still requires the exact same current Juancito event, selected participant, exact +1.5 full-game contract, current actionable price, freshness and final package/correlation gates. FULLVIS/current-inventory closure remains separate.
