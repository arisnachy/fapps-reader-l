# KIRA Ω — MAX 2026 MISSION RESULT

**Final decision:** `NO_PASS_DO_NOT_PIN`  
**Strategy under test:** `MAX 2026` — broad football favorite +1.5, ranked daily, nested T3/T4/T5  
**Calendar target:** 2026-01-01 through 2026-08-12 (224 days)  
**Frozen threshold:** no-vig HOME/AWAY favorite probability `>= 0.60`  
**Outcome use in candidate generation:** `false`  
**Retuning after results:** `none`

## Mission
Determine whether the practical MAX concept could be promoted to the pinned daily strategy because it appeared to combine availability with high survival. The proposed daily output was three nested tickets:
- T3 = ranks 1–3;
- T4 = ranks 1–4;
- T5 = ranks 1–5.

The promotion gate was deliberately strict: enough daily availability to issue the full 3/4/5 stack, plus complete-ticket observed survival >90% and Wilson95 lower bound >=90% for each ticket size, with at least 35 evaluable dates. No threshold reduction, source pruning, date removal, line change, or post-result substitution was authorized.

## V1 — broad domestic Football-Data universe
Preregistration: `MAX_2026_V1_PREREGISTRATION.md` at commit `fcdef13b3f64394cbeff0dbe97bc67c4547bbb2c`.
Run: `31665818336`; job `94340028473`; artifact `9167875032`; artifact ZIP SHA256 `e6021c5c80f5afc67add24c846cb44c444e9dbcc7d0a0b6b247f4aea972bf99e`.

Availability over all 224 calendar days:
- CORE3 (>=3 eligible): **106/224 = 47.3214%**;
- FULL STACK (>=5 eligible): **69/224 = 30.8036%**.

Complete-ticket survival:
- **T3: 98/106 = 92.4528%**, Wilson95 LCB **85.8100%** — observed >90 but strong gate FAIL;
- **T4: 76/84 = 90.4762%**, Wilson95 LCB **82.3174%** — strong gate FAIL;
- **T5: 62/69 = 89.8551%**, Wilson95 LCB **80.5081%** — observed floor FAIL.

A source-code typo (`E4` vs `EC`) was identified, but it cannot rescue V1: both full-stack availability and T5 survival independently miss the frozen promotion gates.

## V2 — universal OddsPortal daily-football universe
Preregistration: `MAX_2026_V2_PREREGISTRATION.md` at commit `d732ce7d17f87eb6ff898ba75ebb1765c555e0d5`.

The intended universe was every football event exposed on the exact-date OddsPortal page after expansion, including domestic leagues, cups and continental competitions. Candidate ranking remained frozen at `p_no-vig >=0.60` and selected participant +1.5.

### Transport integrity finding
Initial universal runs that emitted zero candidates were rejected as invalid evidence. The zero ledger was caused by DOM hydration timing, not by MAX. The parser was then hardened to require the requested date header, historical result rows, and numeric target-date odds before a page could PASS. This changed transport only; the selector and gates remained frozen.

Corrected Aug-10 control:
- **11 eligible MAX candidates**;
- T3 = WIN;
- T4 = WIN;
- T5 = WIN;
- candidate generation used outcomes = false;
- no unresolved ranked settlement.

### Corrected chunked 2026 replication
Workflow: `kira-max-2026-v2-targetdate-chunked.yml`  
Run: `31667722166`; aggregate job `94346943456`; final artifact `9168684439`; artifact ZIP SHA256 `274e2cf4fc3dbf5f672582747ccec2cd4b64e4d4935f5e0a664edbd18b1f954e`.

Combined pre-settlement ledger SHA256: `6e861e9aa96030cb022eda7a482da45cd9e86079841d2dc27c94ee1dd194e468`.

The exact-date transport did **not** recover the full historical calendar. January through June and several July/August dates failed the source-evidence gate. Therefore universal V2 is `EVIDENCE_INCOMPLETE_DO_NOT_PIN`; those failed dates must not be interpreted as NO_BET or zero-candidate days.

On the **33 successfully recovered/evaluable universal dates**:
- **T3: 30/33 = 90.9091%**, Wilson95 LCB **76.4274%** — certainty gate FAIL;
- **T4: 30/33 = 90.9091%**, Wilson95 LCB **76.4274%** — certainty gate FAIL;
- **T5: 29/33 = 87.8788%**, Wilson95 LCB **72.6745%** — observed floor FAIL.

Useful monthly signals inside the recovered block:
- July recovered dates: T3 24/26 = 92.3077%, T4 24/26 = 92.3077%, T5 23/26 = 88.4615%;
- August recovered dates through Aug-12: T3/T4/T5 each 6/7 = 85.7143%.

These monthly slices are descriptive only; they are not independent promotion tests and are too small for the frozen certainty gate.

## Final judgment
`MAX 2026` in its current fixed daily **T3 + T4 + T5** form is **NOT production-certified and must NOT be pinned as the primary strategy**.

Reasons are independent and load-bearing:
1. V1 complete domestic evidence fails the full-stack availability requirement (69/224) and T5 falls below the >90% observed survival floor (62/69 = 89.8551%).
2. V2 adds the broad competitions needed to resemble the practical MAX tickets, but the recovered universal block is incomplete and therefore cannot establish 2026 calendar coverage.
3. Even within the 33 valid universal dates, T5 is only 29/33 = 87.8788%, below the frozen >90% floor; T3/T4 also fail the Wilson-strength requirement.

The practical +1.5 favorite concept remains a useful research/candidate-generation family, and individual days such as 2026-08-10 can produce winning 3/4/5 stacks. That does not justify extrapolating a daily 2026 certainty claim.

## Authorized next research lane
Recover January–June through preregistered **competition/season historical pages** (e.g. OddsHarvester historic mode) while preserving the exact MAX selector, threshold, +1.5 contract and 3/4/5 packaging. This is evidence completion only, not a rescue retune. Until an independent/full-calendar block clears all frozen gates, MAX remains `NO_PIN`.

No sports-betting strategy guarantees future wins; all percentages above are retrospective empirical results under the stated data and rules.
