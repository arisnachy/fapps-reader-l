from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

OUT=Path('artifacts/kira_football_multi3_0304')
SEASON='0304'
LEAGUES=['E0','SP1','D1','I1','F1','N1','P1','SC0','B1']
REQ=['Date','HomeTeam','AwayTeam','B365H','B365D','B365A','FTHG','FTAG']
MIN_SOURCE_LEAGUES=5
MIN_N=35
MIN_LCB=.90


def wilson(w,n,z=1.959963984540054):
    if n<=0:return 0.0,1.0
    p=w/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
    return max(0,c-m),min(1,c+m)

def parse_date(x):
    s=str(x).strip()
    for f in ('%d/%m/%y','%d/%m/%Y'):
        try:return datetime.strptime(s,f).date().isoformat()
        except Exception: pass
    return ''

def write_csv(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)

def decode_rows(raw):
    last=''
    for enc in ('utf-8-sig','latin-1'):
        try:
            text=raw.decode(enc)
            rows=list(csv.reader(io.StringIO(text,newline='')))
            return enc,rows,''
        except UnicodeDecodeError as exc:
            last=f'DECODE:{exc}'
        except csv.Error as exc:
            last=f'CSV_ERROR:{exc}'
    return '',[],last or 'DECODE'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    s=requests.Session();s.headers['User-Agent']='KIRA-MULTI3-validation/1.0'
    source=[]; pregames=[]; outcomes={}; event_seen=set(); dup=0
    for lg in LEAGUES:
        url=f'https://www.football-data.co.uk/mmz4281/{SEASON}/{lg}.csv'
        try:r=s.get(url,timeout=30)
        except Exception as e:
            source.append({'league':lg,'url':url,'status':'SOURCE_UNUSABLE','reason':type(e).__name__});continue
        if r.status_code!=200:
            source.append({'league':lg,'url':url,'http':r.status_code,'status':'SOURCE_UNUSABLE','reason':'HTTP'});continue
        raw=r.content; sha=hashlib.sha256(raw).hexdigest(); enc,rows,err=decode_rows(raw)
        if not rows:
            source.append({'league':lg,'url':url,'bytes':len(raw),'sha256':sha,'status':'SOURCE_UNUSABLE','reason':err});continue
        header=None; header_i=None
        for i,row in enumerate(rows):
            cleaned=[str(x).strip() for x in row]
            if all(c in cleaned for c in REQ):
                header=cleaned;header_i=i;break
        if header is None:
            source.append({'league':lg,'url':url,'bytes':len(raw),'sha256':sha,'raw_rows':max(0,len(rows)-1),'status':'SOURCE_UNUSABLE','reason':'MISSING_COLUMNS','missing':REQ});continue
        idx={c:header.index(c) for c in REQ}; max_idx=max(idx.values()); accepted=0; malformed_short=0; invalid_required=0
        data_rows=rows[header_i+1:]
        for row in data_rows:
            if not row or all(not str(x).strip() for x in row):continue
            if len(row)<=max_idx:
                malformed_short+=1;continue
            vals={c:row[j] for c,j in idx.items()}
            d=parse_date(vals['Date']); home=str(vals['HomeTeam']).strip(); away=str(vals['AwayTeam']).strip()
            try:h=float(vals['B365H']);dr=float(vals['B365D']);a=float(vals['B365A']);hg=int(float(vals['FTHG']));ag=int(float(vals['FTAG']))
            except Exception:
                invalid_required+=1;continue
            if not d or not home or not away or not all(math.isfinite(x) and x>1 for x in (h,dr,a)):
                invalid_required+=1;continue
            key=(d,lg,home,away)
            if key in event_seen:dup+=1;continue
            event_seen.add(key); qh,qd,qa=1/h,1/dr,1/a;den=qh+qd+qa;ph=qh/den
            event_id='FHIST-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            pregames.append({'date':d,'league_code':lg,'HomeTeam':home,'AwayTeam':away,'B365H':h,'B365D':dr,'B365A':a,'p_home_novig':ph,'event_id':event_id})
            outcomes[event_id]={'FTHG':hg,'FTAG':ag};accepted+=1
        source.append({'league':lg,'url':url,'http':r.status_code,'bytes':len(raw),'sha256':sha,'raw_rows':len(data_rows),'accepted_rows':accepted,'malformed_short_rows':malformed_short,'invalid_required_rows':invalid_required,'encoding':enc,'header_row_index':header_i,'status':'PASS'})
    usable=sum(x.get('status')=='PASS' for x in source)
    if usable<MIN_SOURCE_LEAGUES:
        summary={'decision':'SOURCE_GATE_FAIL','usable_leagues':usable,'required':MIN_SOURCE_LEAGUES,'source_audit':source}
        (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');(OUT/'source_audit.json').write_text(json.dumps(source,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2));return 0
    if dup: raise SystemExit(f'CROSS_SOURCE_DUPLICATES={dup}')

    by_date={}
    for r in pregames:
        if r['p_home_novig']>=.75:by_date.setdefault(r['date'],[]).append(r)
    selected=[]
    for d,items in sorted(by_date.items()):
        items=sorted(items,key=lambda x:(-x['p_home_novig'],x['B365H'],x['league_code'],x['HomeTeam'],x['AwayTeam']))[:3]
        for rank,r in enumerate(items,1): selected.append({**r,'date_rank':rank})
    write_csv(OUT/'selected_event_keys_pre_settlement.csv',selected)

    settled=[]
    for r in selected:
        o=outcomes[r['event_id']]; hit=(o['FTHG']+1.5>o['FTAG'])
        settled.append({**r,**o,'hit':hit,'margin':o['FTHG']-o['FTAG']})
    write_csv(OUT/'selected_legs.csv',settled);write_csv(OUT/'failures.csv',[r for r in settled if not r['hit']])

    dates={}
    for r in settled:dates.setdefault(r['date'],[]).append(r)
    bundles=[]
    for d,rows in sorted(dates.items()):
        bundles.append({'date':d,'legs':len(rows),'survived':all(r['hit'] for r in rows),'event_ids':'|'.join(r['event_id'] for r in rows)})
    write_csv(OUT/'daily_bundles.csv',bundles);write_csv(OUT/'bundle_failures.csv',[r for r in bundles if not r['survived']])

    nw=len(settled);ww=sum(r['hit'] for r in settled);nl=len(bundles);wl=sum(r['survived'] for r in bundles)
    leg_l,leg_u=wilson(ww,nw);bun_l,bun_u=wilson(wl,nl)
    team=Counter(r['HomeTeam'] for r in settled);league=Counter(r['league_code'] for r in settled);month=Counter(r['date'][:7] for r in settled);mult=Counter(r['legs'] for r in bundles)
    summary={
      'hypothesis_id':'FOOTBALL_PLUS1_5_MARKET_DOMINANCE_MULTI3_V1','season':SEASON,'usable_leagues':usable,'source_universe':LEAGUES,
      'pregame_event_rows':len(pregames),'eligible_events_pre_cap':sum(len(v) for v in by_date.values()),'selected_legs':nw,'leg_wins':ww,'leg_losses':nw-ww,'leg_rate':ww/nw if nw else 0,'leg_wilson95_lcb':leg_l,'leg_wilson95_ucb':leg_u,
      'candidate_dates':nl,'bundle_wins':wl,'bundle_losses':nl-wl,'bundle_rate':wl/nl if nl else 0,'bundle_wilson95_lcb':bun_l,'bundle_wilson95_ucb':bun_u,
      'date_leg_count_distribution':dict(sorted(mult.items())),'max_legs_date':max(mult) if mult else 0,'max_team':team.most_common(1)[0] if team else None,'max_league':league.most_common(1)[0] if league else None,'max_month':month.most_common(1)[0] if month else None,
      'leg_gate_pass':nw>=MIN_N and leg_l>=MIN_LCB,'bundle_gate_pass':nl>=MIN_N and bun_l>=MIN_LCB,'source_gate_pass':usable>=MIN_SOURCE_LEAGUES,'duplicate_event_keys':dup,
      'decision':'SCIENCE_CERTAINTY_PASS' if (nw>=MIN_N and leg_l>=MIN_LCB and nl>=MIN_N and bun_l>=MIN_LCB) else 'NO_PASS',
      'candidate_generation_used_outcomes':False
    }
    (OUT/'source_audit.json').write_text(json.dumps(source,indent=2),encoding='utf-8');(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
