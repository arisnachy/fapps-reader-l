# KIRA Ω — MAX-N EXTRA16 FAVORITE +1.5 — 2021 STRESS TEST RESULT

**Decision:** `MAXN_HISTORICAL_STRESS_WINNER_N3`  
**Status:** `RETROSPECTIVE_ONLY`  
**Preregistration commit:** `ba78bf6b6729e70fbe1aa12e49e88c515ed915e7`  
**Scorer commit:** `f755f6e8686712f00277d7ae94b86357581cf2d6`  
**Workflow commit:** `009d5d8c8339267a12e7adc3eaaa42262b73a043`  
**Run:** `31664785361`  
**Job:** `94336883080`  
**Artifact:** `9167505763` (`kira-extra16-plus1-5-maxn-2021`)  
**Artifact ZIP SHA256:** `a7e37716fba12b90ff86b72a25b213b2d01b3a3ff1f455f7be3344d06ff72963`

## Frozen selector
Exact same 16-source, 2021, market-average no-vig favorite selector as the accepted MULTI3 engine:
- favorite probability `>=0.60`;
- exact selected participant `+1.5`, full game;
- deterministic ranking `(-p_favorite_novig, selected_price, source, league, Home, Away, HOME-before-AWAY)`;
- outcomes excluded from candidate generation/ranking;
- exact event identity; no duplicate events.

The only extension was to freeze ranks 1..7 before settlement and evaluate ticket prefixes N=3..7 on dates with at least N eligible distinct events.

Pre-settlement ledger SHA256: `e2cb3347971c4616b7db5ab860c588df016282eb033e80e98053a81a1041a240`.
Candidate generation used outcomes: **false**. Duplicate event keys: **0**. Sources: **16/16 PASS**.

## Complete-ticket results

| N | Evaluable dates | Ticket wins | Losses | Survival | Wilson95 LCB | >90 observed | >92 target | LCB>=90 |
|---:|---:|---:|---:|---:|---:|:---:|:---:|:---:|
| 3 | 111 | 107 | 4 | **96.3964%** | **91.0990%** | PASS | PASS | **PASS** |
| 4 | 76 | 69 | 7 | **90.7895%** | 82.1873% | PASS | NO | NO |
| 5 | 52 | 48 | 4 | **92.3077%** | 81.8264% | PASS | **PASS** | NO |
| 6 | 40 | 34 | 6 | **85.0000%** | 70.9277% | NO | NO | NO |
| 7 | 28 | 25 | 3 | **89.2857%** | 72.8041% | NO | NO | NO / TOO_THIN |

## Prefix-leg results
- N3: 328/333 = 98.4985%, leg Wilson LCB 96.5338%.
- N4: 296/304 = 97.3684%, leg Wilson LCB 94.8940%.
- N5: 256/260 = 98.4615%, leg Wilson LCB 96.1118%.
- N6: 234/240 = 97.5000%, leg Wilson LCB 94.6541%.
- N7: 193/196 = 98.4694%, leg Wilson LCB 95.5973%.

## Availability
Across 257 dates with at least one eligible event, full eligible candidate multiplicity (capped at 7 for reporting) was:
- 94 dates with 1;
- 52 with 2;
- 35 with 3;
- 24 with 4;
- 12 with 5;
- 12 with 6;
- 28 with 7+.

Thus dates with at least N were exactly: N3=111, N4=76, N5=52, N6=40, N7=28.

## Interpretation
Under the preregistered stress-test rule, the largest N with >=35 dates, observed ticket survival >90%, and Wilson95 LCB >=90% is **N=3**.

N=5 is a **promising replication target** because its observed complete-ticket survival is 48/52 = 92.31%, but its Wilson LCB is only 81.83%; it is not strong enough to call production-valid. N=6 and N=7 fail the observed >90% floor in this block.

This result does not guarantee future wins and does not promote any N>3 to production. A fresh independent/prospective block is required before changing the operational MAX-N ceiling.
