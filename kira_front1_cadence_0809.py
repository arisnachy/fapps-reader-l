from __future__ import annotations
import csv, io, json, statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

TH=0.75
LEAGUES={'E0':'England Premier League','SP1':'Spain La Liga','D1':'Germany Bundesliga','I1':'Italy Serie A','F1':'France Ligue 1','N1':'Netherlands Eredivisie','P1':'Portugal Primeira Liga','SC0':'Scotland Premiership','B1':'Belgium First Division A'}

def pdate(s):
    for f in ('%d/%m/%y','%d/%m/%Y'):
        try:return datetime.strptime((s or '').strip(),f).date()
        except:pass
    return None

def fnum(x):
    try:return float(x)
    except:return None

games=[]
for code,league in LEAGUES.items():
    url=f'https://www.football-data.co.uk/mmz4281/0809/{code}.csv'
    req=Request(url,headers={'User-Agent':'KIRA-CADENCE-AUDIT/1.0'})
    with urlopen(req,timeout=60) as r: text=r.read().decode('utf-8-sig',errors='replace')
    for row in csv.DictReader(io.StringIO(text)):
        d=pdate(row.get('Date'))
        if d is None: continue
        h,dod,a=(fnum(row.get(k)) for k in ('B365H','B365D','B365A'))
        rec={'date':d,'league_code':code,'league':league,'home':row.get('HomeTeam',''),'away':row.get('AwayTeam',''),'H':h,'D':dod,'A':a}
        if h and dod and a and h>1 and dod>1 and a>1:
            qh,qd,qa=1/h,1/dod,1/a
            rec['p_home_novig']=qh/(qh+qd+qa)
        else: rec['p_home_novig']=None
        games.append(rec)

active_dates=sorted({g['date'] for g in games})
complete_dates=sorted({g['date'] for g in games if g['p_home_novig'] is not None})
eligible=[g for g in games if g['p_home_novig'] is not None and g['p_home_novig']>=TH]
by_date=defaultdict(list)
for g in eligible:by_date[g['date']].append(g)
selected=[]
for d,rows in by_date.items():
    rows.sort(key=lambda x:(-x['p_home_novig'],x['H'],x['league_code'],x['home'],x['away']))
    selected.append(rows[0])
selected.sort(key=lambda x:x['date'])
candidate_dates=[x['date'] for x in selected]
start=min(active_dates); end=max(active_dates)
calendar_days=(end-start).days+1
all_days=[start+timedelta(days=i) for i in range(calendar_days)]
no_candidate_active=sorted(set(active_dates)-set(candidate_dates))
no_candidate_complete=sorted(set(complete_dates)-set(candidate_dates))
no_candidate_calendar=sorted(set(all_days)-set(candidate_dates))
multiple_dates={d:len(v) for d,v in by_date.items() if len(v)>1}
gaps=[(candidate_dates[i]-candidate_dates[i-1]).days for i in range(1,len(candidate_dates))]

def streak(seq):
    if not seq:return 0
    best=cur=1
    for a,b in zip(seq,seq[1:]):
        if (b-a).days==1:cur+=1;best=max(best,cur)
        else:cur=1
    return best

out={
 'hypothesis_id':'FOOTBALL_PLUS1_5_MARKET_DOMINANCE_V1',
 'audit_type':'DESCRIPTIVE_COVERAGE_ONLY_NON_TUNING',
 'threshold_unchanged':TH,
 'source_block':'official Football-Data 0809 same nine frozen leagues',
 'coverage':{
   'first_active_date':start.isoformat(),'last_active_date':end.isoformat(),'calendar_days_in_span':calendar_days,
   'match_active_dates':len(active_dates),'complete_1x2_active_dates':len(complete_dates),
   'eligible_raw_events':len(eligible),'candidate_dates_after_frozen_one_per_date':len(candidate_dates),
   'active_dates_without_candidate':len(no_candidate_active),
   'active_date_candidate_rate':len(candidate_dates)/len(active_dates),
   'active_date_no_candidate_rate':len(no_candidate_active)/len(active_dates),
   'calendar_days_without_candidate':len(no_candidate_calendar),
   'calendar_day_candidate_rate':len(candidate_dates)/calendar_days,
   'calendar_day_no_candidate_rate':len(no_candidate_calendar)/calendar_days,
   'dates_with_multiple_eligible_events':len(multiple_dates),
   'max_eligible_events_same_date':max(multiple_dates.values()) if multiple_dates else 1,
 },
 'cadence':{
   'mean_days_between_candidate_dates':statistics.mean(gaps) if gaps else None,
   'median_days_between_candidate_dates':statistics.median(gaps) if gaps else None,
   'max_days_between_candidate_dates':max(gaps) if gaps else None,
   'longest_consecutive_calendar_days_without_candidate':streak(no_candidate_calendar),
   'candidate_weekday_counts':dict(sorted(Counter(x['date'].strftime('%A') for x in selected).items())),
   'candidate_month_counts':dict(sorted(Counter(x['date'].strftime('%Y-%m') for x in selected).items())),
 },
 'concentration':{
   'selected_team_counts':dict(Counter(x['home'] for x in selected).most_common()),
   'selected_league_counts':dict(Counter(x['league_code'] for x in selected).most_common()),
   'max_team':Counter(x['home'] for x in selected).most_common(1)[0],
   'max_league':Counter(x['league_code'] for x in selected).most_common(1)[0],
 },
 'multiple_eligible_dates':{d.isoformat():n for d,n in sorted(multiple_dates.items())},
 'guard':'Descriptive only. No threshold/selector/tie-break/line/gate changes may be inferred from cadence.'
}
open('cadence_0809.json','w').write(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))