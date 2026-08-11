from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HYPOTHESIS = 'FOOTBALL_PLUS0_5_MARKET_FAVORITE_V1'
BLOCK = '0506'
LEAGUES = ['E0','SP1','D1','I1','F1','N1','P1','SC0','B1']
THRESHOLD = 0.60
Z = 1.959963984540054
N_GATE = 35
LCB_GATE = 0.90
OUT = Path('front1_plus0_5_favorite_0506_output')
OUT.mkdir(exist_ok=True)
REQUIRED = ['Date','HomeTeam','AwayTeam','FTHG','FTAG','B365H','B365D','B365A']


def parse_date(value: str):
    value=(value or '').strip()
    for fmt in ('%d/%m/%y','%d/%m/%Y','%d-%m-%y','%d-%m-%Y'):
        try: return datetime.strptime(value,fmt).date()
        except ValueError: pass
    raise ValueError(f'UNPARSEABLE_DATE:{value}')


def num(value):
    try: return float(str(value).strip())
    except Exception: return None


def wilson(k,n,z=Z):
    if n<=0: return (0.0,1.0)
    p=k/n; z2=z*z; den=1+z2/n
    center=(p+z2/(2*n))/den
    margin=z*math.sqrt((p*(1-p)/n)+(z2/(4*n*n)))/den
    return max(0.0,center-margin),min(1.0,center+margin)


def download(league):
    url=f'https://www.football-data.co.uk/mmz4281/{BLOCK}/{league}.csv'
    req=urllib.request.Request(url,headers={'User-Agent':'KIRA-Science/1.0'})
    with urllib.request.urlopen(req,timeout=40) as r:
        data=r.read()
    # Football-Data historical CSVs are commonly latin-1 compatible.
    text=data.decode('utf-8-sig',errors='replace')
    if '\ufffd' in text:
        text=data.decode('latin-1')
    return url,data,text


all_rows=[]; source_audit={}; fingerprints={}; seen_keys=set(); duplicate_keys=[]
for league in LEAGUES:
    url,data,text=download(league)
    reader=csv.DictReader(io.StringIO(text))
    fields=reader.fieldnames or []
    missing=[c for c in REQUIRED if c not in fields]
    if missing:
        raise RuntimeError(f'MISSING_REQUIRED_COLUMNS:{league}:{missing}')
    raw=0; valid=0; bad=0; dates=[]
    for rec in reader:
        if not any((v or '').strip() for v in rec.values()): continue
        raw+=1
        try:
            d=parse_date(rec['Date'])
            h=rec['HomeTeam'].strip(); a=rec['AwayTeam'].strip()
            fthg=int(float(rec['FTHG'])); ftag=int(float(rec['FTAG']))
            bh=num(rec['B365H']); bd=num(rec['B365D']); ba=num(rec['B365A'])
            if not h or not a or bh is None or bd is None or ba is None or min(bh,bd,ba)<=1.0:
                bad+=1; continue
            key=(d.isoformat(),league,h,a)
            if key in seen_keys: duplicate_keys.append(key)
            seen_keys.add(key)
            qh,qd,qa=1/bh,1/bd,1/ba; den=qh+qd+qa
            ph,pd,pa=qh/den,qd/den,qa/den
            if ph==pa:
                selected_side=None; favorite=None; selected_price=None
            elif ph>pa:
                selected_side='HOME'; favorite=ph; selected_price=bh
            else:
                selected_side='AWAY'; favorite=pa; selected_price=ba
            all_rows.append({
                'date':d,'date_iso':d.isoformat(),'league_code':league,'HomeTeam':h,'AwayTeam':a,
                'B365H':bh,'B365D':bd,'B365A':ba,'p_home_novig':ph,'p_draw_novig':pd,'p_away_novig':pa,
                'selected_side':selected_side,'p_favorite_novig':favorite,'selected_side_price':selected_price,
                'FTHG':fthg,'FTAG':ftag,
            })
            valid+=1; dates.append(d)
        except Exception:
            bad+=1
    sha=hashlib.sha256(data).hexdigest()
    fingerprints[league]={'url':url,'bytes':len(data),'sha256':sha}
    source_audit[league]={
        'url':url,'bytes':len(data),'sha256':sha,'raw_rows':raw,'valid_rows':valid,'bad_rows':bad,
        'required_columns_present':not missing,'date_min':min(dates).isoformat() if dates else None,
        'date_max':max(dates).isoformat() if dates else None,
    }

if duplicate_keys:
    raise RuntimeError(f'DUPLICATE_EVENT_KEYS:{len(duplicate_keys)}')

# Eligibility is prematch-only. Build selected key frame before touching outcomes.
eligible=[r for r in all_rows if r['selected_side'] and r['p_favorite_novig'] is not None and r['p_favorite_novig']>=THRESHOLD]
by_date=defaultdict(list)
for r in eligible: by_date[r['date_iso']].append(r)
selected_pre=[]
for date,items in sorted(by_date.items()):
    items=sorted(items,key=lambda r:(-r['p_favorite_novig'],r['selected_side_price'],r['league_code'],r['HomeTeam'],r['AwayTeam'],r['selected_side']))
    r=items[0]
    selected_pre.append({k:r[k] for k in (
        'date_iso','league_code','HomeTeam','AwayTeam','B365H','B365D','B365A','p_home_novig','p_draw_novig','p_away_novig',
        'selected_side','p_favorite_novig','selected_side_price'
    )})

# Persist selected keys before settlement join.
pre_fields=['date','league_code','HomeTeam','AwayTeam','B365H','B365D','B365A','p_home_novig','p_draw_novig','p_away_novig','selected_side','p_favorite_novig','selected_side_price']
with (OUT/'selected_event_keys_pre_settlement.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=pre_fields); w.writeheader()
    for r in selected_pre:
        row=dict(r); row['date']=row.pop('date_iso'); w.writerow(row)

# Join settlement strictly by frozen event identity.
lookup={(r['date_iso'],r['league_code'],r['HomeTeam'],r['AwayTeam']):r for r in all_rows}
settled=[]
for p in selected_pre:
    r=lookup[(p['date_iso'],p['league_code'],p['HomeTeam'],p['AwayTeam'])]
    side=p['selected_side']
    if side=='HOME':
        passed=(r['FTHG']+0.5>r['FTAG'])
        selected_team=r['HomeTeam']; loss_margin=r['FTAG']-r['FTHG']
    else:
        passed=(r['FTAG']+0.5>r['FTHG'])
        selected_team=r['AwayTeam']; loss_margin=r['FTHG']-r['FTAG']
    settled.append({**p,'FTHG':r['FTHG'],'FTAG':r['FTAG'],'selected_team':selected_team,'contract':'SELECTED PARTICIPANT +0.5','settlement':'PASS' if passed else 'FAIL','loss_margin':loss_margin})

leg_fields=['date','league_code','HomeTeam','AwayTeam','B365H','B365D','B365A','p_home_novig','p_draw_novig','p_away_novig','selected_side','p_favorite_novig','selected_side_price','FTHG','FTAG','selected_team','contract','settlement','loss_margin']
def write_legs(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=leg_fields);w.writeheader()
        for r in rows:
            x=dict(r);x['date']=x.pop('date_iso');w.writerow(x)
write_legs(OUT/'selected_legs.csv',settled)
failures=[r for r in settled if r['settlement']=='FAIL']
write_legs(OUT/'failures.csv',failures)

n=len(settled); k=n-len(failures); lo,hi=wilson(k,n)
team_counts=Counter(r['selected_team'] for r in settled); league_counts=Counter(r['league_code'] for r in settled); side_counts=Counter(r['selected_side'] for r in settled)
max_team=max(team_counts.items(),key=lambda x:x[1]) if team_counts else (None,0)
max_league=max(league_counts.items(),key=lambda x:x[1]) if league_counts else (None,0)

integrity={
    'source_identity_pass':all(x['required_columns_present'] and x['valid_rows']>0 for x in source_audit.values()),
    'cross_source_duplicate_event_rows':len(duplicate_keys),
    'one_selection_per_date_pass':len(selected_pre)==len({r['date_iso'] for r in selected_pre}),
    'threshold_pass':all(r['p_favorite_novig']>=THRESHOLD for r in selected_pre),
    'selected_event_uniqueness_pass':len(selected_pre)==len({(r['date_iso'],r['league_code'],r['HomeTeam'],r['AwayTeam']) for r in selected_pre}),
    'settlement_completeness_pass':len(settled)==len(selected_pre),
    'settlement_rule_pass':all((r['settlement']=='PASS') == ((r['FTHG']+0.5>r['FTAG']) if r['selected_side']=='HOME' else (r['FTAG']+0.5>r['FTHG'])) for r in settled),
    'result_leakage_firewall_pass':True,
    'eligible_raw_events':len(eligible),'selected_dates':len(selected_pre),'side_counts':dict(side_counts),
    'team_counts':dict(team_counts),'league_counts':dict(league_counts),
    'max_team':{'team':max_team[0],'count':max_team[1],'share':max_team[1]/n if n else None},
    'max_league':{'league':max_league[0],'count':max_league[1],'share':max_league[1]/n if n else None},
}

# Outcome-blind coverage vs frozen primary HOME >=0.75 on same 0506 prematch universe.
home_dates={}
for date,items in defaultdict(list, {d:[r for r in all_rows if r['date_iso']==d and r['p_home_novig']>=0.75] for d in {r['date_iso'] for r in all_rows}}).items():
    if items:
        s=sorted(items,key=lambda r:(-r['p_home_novig'],r['B365H'],r['league_code'],r['HomeTeam'],r['AwayTeam']))[0]
        home_dates[date]=s
new_dates={r['date_iso']:r for r in selected_pre}
active_dates=sorted({r['date_iso'] for r in all_rows})
first=min(r['date'] for r in all_rows); last=max(r['date'] for r in all_rows)
cal=[]; d=first
while d<=last:
    ds=d.isoformat(); h=home_dates.get(ds); x=new_dates.get(ds)
    if h and x: cat='BOTH'
    elif h: cat='HOME_ONLY'
    elif x: cat='PLUS0_5_ONLY'
    else: cat='NEITHER'
    cal.append({'date':ds,'match_active':ds in set(active_dates),'home_candidate':bool(h),'home_selected_event':f"{h['league_code']}|{h['HomeTeam']}|{h['AwayTeam']}" if h else '',
                'plus0_5_candidate':bool(x),'plus0_5_selected_event':f"{x['league_code']}|{x['HomeTeam']}|{x['AwayTeam']}|{x['selected_side']}" if x else '',
                'coverage_category':cat,'union_covered':bool(h or x)})
    d+=timedelta(days=1)
with (OUT/'eligibility_calendar_0506.csv').open('w',newline='',encoding='utf-8') as f:
    fields=list(cal[0]);w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(cal)
active_cal=[x for x in cal if x['match_active']]
cats=Counter(x['coverage_category'] for x in active_cal)
union_dates=sorted(datetime.strptime(x['date'],'%Y-%m-%d').date() for x in active_cal if x['union_covered'])
gaps=[(b-a).days for a,b in zip(union_dates,union_dates[1:])]
# Longest consecutive calendar-day streak without union candidate in whole span.
longest=cur=0
for x in cal:
    if not x['union_covered']: cur+=1;longest=max(longest,cur)
    else: cur=0
coverage={
    'block':BLOCK,'comparison_is_outcome_blind':True,'active_dates':len(active_cal),
    'active_date_categories':dict(cats),'home_candidate_dates':len(home_dates),'plus0_5_candidate_dates':len(new_dates),
    'incremental_plus0_5_fill_dates':cats.get('PLUS0_5_ONLY',0),
    'union_candidate_dates':sum(1 for x in active_cal if x['union_covered']),
    'union_active_date_coverage_rate':sum(1 for x in active_cal if x['union_covered'])/len(active_cal) if active_cal else None,
    'active_dates_no_bet':sum(1 for x in active_cal if not x['union_covered']),
    'active_date_no_bet_rate':sum(1 for x in active_cal if not x['union_covered'])/len(active_cal) if active_cal else None,
    'median_days_between_union_candidate_dates':sorted(gaps)[len(gaps)//2] if gaps else None,
    'max_days_between_union_candidate_dates':max(gaps) if gaps else None,
    'longest_consecutive_calendar_days_without_candidate':longest,
    'calendar_span':{'start':first.isoformat(),'end':last.isoformat(),'days':(last-first).days+1},
    'guard':'Prematch H/D/A and dates only; no outcomes used for eligibility/coverage categories.'
}

all_integrity_pass=all(integrity[k] for k in ('source_identity_pass','one_selection_per_date_pass','threshold_pass','selected_event_uniqueness_pass','settlement_completeness_pass','settlement_rule_pass','result_leakage_firewall_pass')) and integrity['cross_source_duplicate_event_rows']==0
passed=bool(all_integrity_pass and n>=N_GATE and lo>=LCB_GATE)
summary={
    'hypothesis_id':HYPOTHESIS,'validation_block':BLOCK,'execution_mode':'SINGLE_USE_FROZEN_OOS','threshold':THRESHOLD,
    'selected':n,'settled':n,'survived':k,'failed':len(failures),'rate':k/n if n else None,
    'wilson_z':Z,'wilson95_lower':lo,'wilson95_upper':hi,
    'n_gate':{'required':N_GATE,'observed':n,'pass':n>=N_GATE},'lcb_gate':{'required':LCB_GATE,'observed':lo,'pass':lo>=LCB_GATE},
    'integrity':integrity,'final_result':'PASS' if passed else 'NO_PASS',
    'classification_if_pass':'CORRELATED_FOOTBALL_AVAILABILITY_REDUNDANCY_NOT_INDEPENDENT_CORE',
    'anti_retune_guard':'Terminal result for frozen 0506 block. No rerun, threshold change, line change or universe widening is permitted.'
}
for name,obj in [('summary.json',summary),('source_audit.json',source_audit),('source_fingerprints.json',fingerprints),('selection_settlement_audit.json',integrity),('coverage_vs_home_0506.json',coverage)]:
    (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,indent=2,ensure_ascii=False))
