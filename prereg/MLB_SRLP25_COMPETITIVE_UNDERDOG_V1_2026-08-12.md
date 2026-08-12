# KIRA Ω — MLB SRL +2.5 COMPETITIVE UNDERDOG V1

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / TARGET BLOCKS UNSCORED

## Purpose
Test a materially different Juancito-native `Super Run Line +2.5` selector on competitive underdogs, rather than the failed strong-team standings-gap V1.

## Disjunction
No pitcher, Elo, proprietary rating, park, betting-price, M2/M21 feature or target score is used. Inputs are only each team's completed MLB regular-season games strictly before the target date: W/L, runs for and runs against.

## Frozen selector
For every MLB regular-season target game, after both teams have >=40 prior completed regular-season games:
- identify the team with strictly lower prior win percentage as selected side;
- selected prior win percentage must be **>=0.400 and <0.500**;
- opponent prior win percentage must be **>0.500 and <=0.600**;
- prior win-percentage gap `(opponent - selected)` must be **>=0.040 and <=0.120**;
- selected prior run differential/game must be **>= -0.60**;
- opponent prior run differential/game must be **<= +0.80**;
- if tie/ambiguous state: no candidate.

All qualifying games enter date pool; max TWO distinct games/date ranked by:
1. smaller win-percentage gap;
2. higher selected-team run differential/game;
3. lower opponent run differential/game;
4. lexical selected team/opponent/game id.

All games on a calendar date are selected before any same-day result updates state.

## Contract
Exact Juancito target: selected team `PROPUESTAS DE MLB - Super Run Line +2.5`, full game. Science WIN iff selected team loses by at most 2 runs or wins; LOSS iff loses by 3+.

No +1.5/+3.5, standard RL, F5, moneyline or total substitution. Live production additionally requires that Juancito's actual +2.5 side equals the selected team.

## Validation
Official MLB StatsAPI regular-season final games only.
- DEV: 2023 regular season.
- independent OOS: 2024 regular season, unopened unless DEV passes.

## User Gate90
Each block:
- >=100 selected legs;
- >=60 candidate dates;
- observed leg survival >90%;
- observed daily-bundle survival >90%;
- temporal firewall, one-event-one-leg, max2/date and complete settlement PASS.

Wilson95 intervals are diagnostics only. Any failure closes V1, no threshold/line/year rescue.

## Coverage/production
Terminal OOS PASS permits outcome-blind 2025 candidate reconstruction. Production requires current exact Juancito selected-side +2.5, freshness and settlement equivalence.
