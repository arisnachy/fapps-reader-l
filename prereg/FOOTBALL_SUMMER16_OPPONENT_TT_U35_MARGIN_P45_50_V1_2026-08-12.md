# KIRA Ω — SUMMER16 OPPONENT TT U3.5 — MARGINAL P45-50 V1

Frozen: 2026-08-12 America/Santo_Domingo
Status: PREREGISTERED / TARGET BLOCKS UNSCORED

Purpose: test summer matches where the stronger HOME/AWAY participant has no-vig probability 0.45..0.50, a band structurally disjoint from every admitted p>=0.50 football family and potentially present on red weekdays.

Population/source: `ARG,AUT,BRA,CHN,DNK,FIN,IRL,JPN,MEX,NOR,POL,ROU,RUS,SWE,SWZ,USA`, required `Date,Home,Away,League,AvgCH,AvgCD,AvgCA,HG,AG`. Every target-year source must pass; no source/column substitution.

Frozen selector:
- normalize AvgCH/AvgCD/AvgCA implied probabilities;
- choose unique higher-probability HOME/AWAY participant;
- require **0.45 <= selected no-vig probability < 0.50**;
- OPPONENT TEAM TOTAL UNDER 3.5 full match;
- max THREE distinct events/date;
- rank probability desc, selected-side price asc, source/league/home/away/side lexical;
- target HG/AG cannot create/remove/rank candidates; one event max one leg.

Settlement: WIN iff opponent scores <=3; LOSS iff >=4. No line/wrapper substitute.

Sequential validation: DEV calendar 2013; OOS calendar 2014 unopened unless DEV passes.

User Gate90 each block: all16 source gates PASS; >=250 selected legs; >=120 candidate dates; observed leg survival >90%; observed daily-bundle survival >90%; outcome-blind selection; unique events; max3/date; complete settlement. Wilson95 diagnostics only.

Failure closes V1 with no threshold/year/source rescue. Terminal OOS PASS permits outcome-blind 2025 reconstruction and literal event dedupe. Production still requires exact current Juancito opponent Team Total U3.5 market/line/price/freshness/accumulator/settlement.
