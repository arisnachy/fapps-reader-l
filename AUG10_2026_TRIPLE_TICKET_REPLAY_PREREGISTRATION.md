# KIRA Ω — 2026-08-10 TRIPLE-TICKET REPLAY — PREREGISTRATION

Purpose: replay 2026-08-10 outcome-blind under the new daily output: one CORE-3, one CORE-4, one CORE-5 built as prefixes of the same frozen ranking.

Frozen universe and selector:
- sources exactly ARG,AUT,BRA,CHN,DNK,FIN,IRL,JPN,MEX,NOR,POL,ROU,RUS,SWE,SWZ,USA;
- target date exactly 2026-08-10;
- use only prematch 1X2 market-average prices AvgCH/AvgCD/AvgCA for eligibility/ranking;
- compute no-vig HOME/AWAY probabilities; select the stronger HOME/AWAY participant only if p_favorite >= 0.60;
- exact proposed contract: selected participant +1.5, full game;
- exact event identity; distinct events only;
- ranking unchanged from accepted EXTRA16 engine: (-p_favorite_novig, selected_price, source, league, Home, Away, HOME-before-AWAY);
- freeze ranks 1..5 before outcome settlement;
- candidate generation/ranking must not use HG/AG or any result field.

Tickets, if enough eligible distinct events exist:
- CORE-3 = ranks 1..3;
- CORE-4 = ranks 1..4;
- CORE-5 = ranks 1..5.

Settlement is joined only after the rank1..5 ledger is written. A +1.5 leg survives iff selected participant goal differential is >= -1 (equivalently gd + 1.5 > 0).

This is a retrospective replay / demonstration, not an independent OOS certification and not a guarantee of future wins. No threshold, source, line, ranking, or ticket composition may be changed after settlement.