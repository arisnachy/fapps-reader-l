# KIRA Ω — EURO FRINGE3 TIER-B P055 +1.5 TRANSPORT V1

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / OUTCOMES UNOPENED

Transport the already-frozen Tier-B P055 selector unchanged into Football-Data leagues `T1`, `G1`, `EC` (Turkey top division, Greece top division, English Conference/National League where source exists).

Frozen selector/contract:
- `AvgCH, AvgCD, AvgCA` closing market averages only;
- normalize implied probabilities;
- choose unique HOME/AWAY favorite;
- favorite probability >=0.55;
- exact selected participant +1.5 goals, full match;
- max3 distinct events/date globally within family;
- deterministic rank by probability desc, selected price asc, league/home/away/side;
- one event one leg; target result not used in selection.

Sequential sealed blocks:
- DEV `2223`;
- OOS `2324`, unopened unless DEV passes.

User Gate90 each block:
- all available frozen league sources must satisfy required-column gate; a league whose Football-Data URL is genuinely absent is recorded `SOURCE_ABSENT` and the experiment proceeds only if at least two of the three frozen leagues are usable in BOTH blocks;
- >=100 selected legs;
- >=60 candidate dates;
- observed leg survival >90%;
- observed daily-bundle survival >90%;
- outcome-blind generation, uniqueness, max3/date, settlement complete.

Wilson95 intervals are diagnostics, not vetoes under User Gate90. No source replacement, threshold change or line rescue after this freeze.

Only terminal OOS PASS authorizes outcome-blind common-window coverage reconstruction. Production still requires exact current Juancito selected-team +1.5 availability and freshness.
