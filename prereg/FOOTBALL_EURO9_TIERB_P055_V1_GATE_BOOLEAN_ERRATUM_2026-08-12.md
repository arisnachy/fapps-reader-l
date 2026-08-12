# KIRA Ω — EURO9 TIER-B P055 V1 — GATE BOOLEAN ERRATUM

Frozen: 2026-08-12 America/Santo_Domingo

The first DEV execution of `FOOTBALL_EURO9_FAVORITE_PLUS1_5_MULTI3_TIERB_P055_TRANSPORT_V1` produced an internally contradictory terminal label caused by a code-level boolean inversion, not by a sports/gate failure.

Immutable first DEV evidence:
- selected ledger SHA256: `f17e823ce6bd039eb6bec116075065f9eaeb064b8ebceae203ea42a99ba83daf`;
- selected legs: 438;
- leg wins: 428/438 = 97.7169%;
- leg Wilson95 LCB: 95.8488%;
- candidate dates: 182;
- daily bundle wins: 172/182 = 94.5055%;
- bundle Wilson95 LCB: 90.1826%;
- all source, n, rate, Wilson, uniqueness, max3/date and settlement gates were `true`;
- `candidate_generation_used_outcomes` was correctly `false`.

Bug: the scorer placed `candidate_generation_used_outcomes: false` directly inside the dictionary passed to Python `all(gates.values())`. Therefore outcome-blind generation was incorrectly treated as a failing boolean.

## Frozen correction boundary

The original selector, sources, thresholds, line, cap, ranking, outcomes and settlement code remain immutable. No sports result may be changed or removed.

The only authorized correction is semantic inversion of that audit field when deciding PASS:
- required condition = `candidate_generation_used_outcomes is False`;
- equivalently expose it as `candidate_generation_outcome_blind: True`.

Before OOS can open, the corrected runner MUST reproduce the exact DEV selected ledger SHA256 above and all substantive preregistered gates must still pass. Any DEV ledger mismatch closes execution and OOS stays sealed.

OOS 2324 remains unopened at the time of this erratum. It may be fetched/scored only after the exact DEV ledger reproduction and corrected boolean gate pass. No other code/gate rescue is authorized.
