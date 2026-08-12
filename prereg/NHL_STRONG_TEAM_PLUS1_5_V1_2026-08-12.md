# KIRA Ω — NHL STRONG-TEAM +1.5 V1 — PREREGISTRATION

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / OUTCOMES UNOPENED

## Purpose
Create an independent winter daily-event family using the exact hockey full-game selected-team +1.5 goal/puck-line settlement, subject to later Juancito contract binding.

## Frozen data source
Official NHL public API only: `api-web.nhle.com/v1/club-schedule-season/{TEAM}/{SEASON}`. Fetch all NHL clubs for each block, dedupe by NHL game id, regular season only. Source/API failure is fail-closed.

## Frozen pregame selector
For each target date, using completed regular-season games STRICTLY BEFORE that date:
- both teams prior games >=25;
- selected team prior win percentage >=0.650;
- opponent prior win percentage <=0.500;
- win-percentage gap >=0.150;
- selected team prior goal differential/game >= +0.60;
- opponent prior goal differential/game <= 0.00;
- if neither or both sides qualify: no candidate.

All qualifying distinct games enter the date pool. Retain max TWO games/date, ranked pregame by:
1. larger win-percentage gap;
2. larger selected-team goal differential/game;
3. lower opponent win percentage;
4. lexical selected team/opponent/game id.

Target-day scores cannot create/remove/rank candidates. All games on the same date are selected before any result from that date updates state.

## Frozen contract / settlement
- sport: NHL regular season;
- selected team +1.5 goals, full game;
- WIN if selected team final score +1.5 > opponent final score;
- LOSS if selected team loses by 2+ goals;
- no moneyline/total/team-total/period substitution.

Overtime/shootout final official NHL score is used exactly as published for full-game settlement; later Juancito rule binding must prove operator equivalence.

## Sequential validation
- DEV season 2022-23 (`20222023`).
- independent OOS season 2023-24 (`20232024`), never fetched/scored unless DEV passes.

## User Gate90
Each block requires:
- >=100 selected legs;
- >=60 candidate dates;
- observed leg survival >90%;
- observed whole daily-bundle survival >90%;
- source completeness, one-event-one-leg, temporal firewall, max2/date and complete settlement PASS.

Wilson95 intervals are reported as diagnostics, not vetoes under User Gate90.

Any DEV/OOS observed-rate failure closes V1; no threshold/line rescue.

## Mission use
Only terminal OOS PASS may be reconstructed outcome-blind over the mission common window and counted as science-qualified candidate coverage. Production requires exact fresh Juancito NHL +1.5 availability and settlement binding.
