# KIRA Ω — MLB SRL +2.5 STANDINGS-GAP V1 — PREREGISTRATION

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / OUTCOMES UNOPENED
Operational certainty policy: user-authorized Gate V2, >90%; for promotion this experiment conservatively requires Wilson95 LCB >0.90 at both leg and daily-bundle levels.

## Purpose

Test a genuinely new, Juancito-native summer multi-event family for the exact currently observed `Super Run Line +2.5` contract without inheriting the contaminated legacy M2.1 shadow +2.5 result.

## Contamination disjunction

Legacy M2.1 used rating_prob, elo_prob, rating_pre, pitcher_rgs, rgs_diff, pitcher_adj_diff, a Coors veto and a June-Sep population. This V1 uses NONE of those fields and no starting-pitcher, betting-odds, Elo, proprietary rating, park or M2/M21 signal.

The only selector inputs are each team's own completed MLB regular-season games strictly BEFORE the target date: wins, losses, runs scored and runs allowed.

## Exact frozen sports population

- MLB regular season only.
- Exclude spring training, postseason, exhibitions and suspended/uncompleted games from both prior-state calculation and target settlement until officially completed.
- One target game is one event; both sides of the same game can never create two legs.
- No target-game score/result may enter candidate creation, ranking or eligibility.

## Frozen pregame selector

For each scheduled target game, compute separately for both teams using completed regular-season games before that target game's calendar date:

- prior games >= 40 for BOTH teams;
- selected team prior win percentage >= 0.600;
- opponent prior win percentage <= 0.500;
- win-percentage gap `(selected_wpct - opponent_wpct) >= 0.120`;
- selected team prior run differential per game `(runs_for-runs_against)/games >= +0.50`;
- if both sides somehow satisfy or identity/state is unresolved: NO CANDIDATE.

All qualifying games on a date are candidates. For operational packaging, retain at most TWO distinct games/date, ranked deterministically by:

1. larger win-percentage gap;
2. larger selected-team prior run-differential/game;
3. larger selected-team prior win percentage;
4. lexical selected team then opponent.

No target outcome, future game, bookmaker price or gap-date coverage is used for ranking.

## Frozen wager contract

- sport: MLB;
- Juancito family: `PROPUESTAS DE MLB - Super Run Line`;
- exact selected-side line: `+2.5` runs;
- game scope: full game, subject to exact operator SRL settlement equivalence being finalized separately;
- scientific settlement for completed games: WIN if selected team loses by 0, 1 or 2 runs, ties are impossible in completed MLB; LOSS if selected team loses by 3+ runs; selected-team wins are WIN.
- no +3.5/+4.5 substitution; no standard Run Line -1.5 transfer; no F5/first-half, moneyline, total, team total or alternate architecture substitution.

## Frozen validation

Sequential blocks, with the later block remaining sealed unless the earlier gate passes:

- DEV: MLB 2022 regular season.
- Independent OOS: MLB 2023 regular season.

The scorer may fetch/process 2022 first. It MUST NOT request or score 2023 if DEV fails.

## Promotion gates

DEV must satisfy ALL:
- selected legs >= 100;
- candidate dates >= 60;
- leg observed survival > 90%;
- leg Wilson95 LCB > 0.90;
- daily bundle survival > 90%;
- daily bundle Wilson95 LCB > 0.90;
- source completeness / temporal-firewall / one-event-one-leg audits PASS.

Only then may OOS 2023 be opened. OOS must independently satisfy the same gates. No threshold/selector/ranking/line change between DEV and OOS.

## Coverage boundary

Even a terminal science PASS contributes zero production legs until Juancito exact SRL +2.5 period/settlement/actionability is fully bound and the current exact event/side/+2.5 quote is fresh. Historical coverage impact is measured only after terminal OOS PASS and with same-event/event-identity dedupe against existing families.

## Stop rule

Any DEV or OOS gate failure closes V1 exactly as written. No micro-tuning, threshold rescue, line widening or reopening a failed block.
