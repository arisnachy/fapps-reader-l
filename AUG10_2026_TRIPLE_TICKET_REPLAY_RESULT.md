# KIRA Ω — 2026-08-10 TRIPLE-TICKET REPLAY RESULT

**Status:** `RETROSPECTIVE_REPLAY_ONLY`  
**Preregistration commit:** `e3d4abcc9ef583db028ae83889aae078b4f93394`  
**Scorer commit:** `55894e0559a9da62194610a6a3312be949435a9b`  
**Workflow commit:** `660136dabe3c2da0cc0679b978ba46fdff3de91a`  
**Run:** `31665146193`  
**Job:** `94337993738`  
**Artifact:** `9167631473`  
**Artifact ZIP SHA256:** `6aa2adcd5446e620841bee840e3ecda914e2eec2e8af6feb463619598078e1d6`

## Frozen rule
- target date exactly 2026-08-10;
- sources exactly ARG,AUT,BRA,CHN,DNK,FIN,IRL,JPN,MEX,NOR,POL,ROU,RUS,SWE,SWZ,USA;
- market-average pregame 1X2 only;
- no-vig favorite probability >=0.60;
- exact selected participant +1.5 full game;
- same deterministic ranking as EXTRA16;
- ranks 1..5 frozen before outcome settlement;
- candidate generation used outcomes: false;
- duplicate event keys: 0.

## Candidate pool
Only **1** eligible distinct event was found on 2026-08-10:
1. Sweden Allsvenskan — Sirius vs Brommapojkarna — selected **Sirius +1.5**; pregame selected 1X2 price 1.41; no-vig favorite probability **65.4235%**.

Pre-settlement ledger SHA256: `fbe6c9780d2622ace0c85ae879b42ca5ed82df83d0b4eac2ff3ee5dd9dc64d19`.

## Triple-ticket output
- CORE-3: `NOT_ENOUGH_ELIGIBLE` (1 available)
- CORE-4: `NOT_ENOUGH_ELIGIBLE` (1 available)
- CORE-5: `NOT_ENOUGH_ELIGIBLE` (1 available)

## Interpretation
The strict validated EXTRA16 layer could not produce the new daily 3/4/5 ticket stack on this date. This is a coverage failure, not a settlement failure. It directly demonstrates why a separately preregistered and validated universal expansion layer is still required; no new competitions or lower thresholds may be silently treated as certified EXTRA16 legs.