from __future__ import annotations
import csv,io,json,hashlib,math
from collections import Counter
from datetime import datetime
from pathlib import Path
import requests
OUT=Path('artifacts/kira_summer_favorite_plus1_5_multi3_avgc_2023');OUT.mkdir(parents=True,exist_ok=True)
SOURCES={'BRA':'https://www.football-data.co.uk/new/BRA.csv','USA':'https://www.football-data.co.uk/new/USA.csv'}
REQ=['Country','League','Season','Date','Home','Away','AvgCH','AvgCD','AvgCA','HG','AG']
YEAR=2023;TH=.60;MAX_PER_DATE=3;MIN_N=35;MIN_LCB=.92

def wilson(w,n,z=1.959963984540054):
    if n<=0:return 0.0,1.0
    p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
    return max(0,c-m),min(1,c+m)
def parse_date(s):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(s).strip(),f).date()
        except:pass
    return None
def write_csv(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
    sess=requests.Session();sess.headers['User-Agent']='KIRA-SUMMER-AVGC15-M3/1.0'
    audit=[];pregame=[];outcomes={};seen=set();dups=0
    for code,url in SOURCES.items():
        r=sess.get(url,timeout=60);r.raise_for_status();raw=r.content;file_sha=hashlib.sha256(raw).hexdigest()
        rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))));h=[x.strip() for x in rows[0]];miss=[c for c in REQ if c not in h]
        if miss:audit.append({'source':code,'status':'MISSING_COLUMNS','missing':miss});continue
        idx={c:h.index(c) for c in REQ};mx=max(idx.values());year_raw=[];accepted=0
        # First pass creates pregame universe and an outcome map, but selection never reads the outcome map.
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=parse_date(row[idx['Date']])
            if d is None or d.year!=YEAR:continue
            year_raw.append(','.join(row))
            home=row[idx['Home']].strip();away=row[idx['Away']].strip();league=row[idx['League']].strip()
            try:h1=float(row[idx['AvgCH']]);dr=float(row[idx['AvgCD']]);a1=float(row[idx['AvgCA']]);hg=int(float(row[idx['HG']]));ag=int(float(row[idx['AG']]))
            except:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h1,dr,a1)):continue
            qh,qd,qa=1/h1,1/dr,1/a1;den=qh+qd+qa;ph,pa=qh/den,qa/den
            if ph==pa:continue
            side='HOME' if ph>pa else 'AWAY';pf=max(ph,pa);price=h1 if side=='HOME' else a1;entity=home if side=='HOME' else away
            if pf<TH:continue
            key=(d.isoformat(),code,league,home,away)
            if key in seen:dups+=1;continue
            seen.add(key);eid='FSAV-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            pregame.append({'date':d.isoformat(),'source':code,'league':league,'Home':home,'Away':away,'selected_side':side,'selected_entity':entity,'AvgCH':h1,'AvgCD':dr,'AvgCA':a1,'selected_price':price,'p_favorite_novig':pf,'event_id':eid})
            outcomes[eid]={'HG':hg,'AG':ag};accepted+=1
        audit.append({'source':code,'status':'PASS','file_sha256':file_sha,'target_year_rows_sha256':hashlib.sha256('\n'.join(year_raw).encode()).hexdigest(),'target_year_rows':len(year_raw),'eligible_pre_cap':accepted})
    if sum(x.get('status')=='PASS' for x in audit)!=2:
        s={'decision':'SOURCE_GATE_FAIL','source_audit':audit};(OUT/'summary.json').write_text(json.dumps(s,indent=2),encoding='utf-8');print(json.dumps(s,indent=2));return
    if dups:raise SystemExit(f'DUPLICATES={dups}')
    by={}
    for x in pregame:by.setdefault(x['date'],[]).append(x)
    selected=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(-x['p_favorite_novig'],x['selected_price'],x['source'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:MAX_PER_DATE]
        for rank,x in enumerate(rr,1):selected.append({**x,'date_rank':rank})
    write_csv(OUT/'selected_event_keys_pre_settlement.csv',selected)
    settled=[]
    for x in selected:
        o=outcomes[x['event_id']];gd=(o['HG']-o['AG']) if x['selected_side']=='HOME' else (o['AG']-o['HG']);hit=gd+1.5>0
        settled.append({**x,**o,'selected_goal_diff':gd,'hit':hit})
    write_csv(OUT/'selected_legs.csv',settled);write_csv(OUT/'failures.csv',[x for x in settled if not x['hit']])
    dates={}
    for x in settled:dates.setdefault(x['date'],[]).append(x)
    bundles=[]
    for d,rr in sorted(dates.items()):bundles.append({'date':d,'legs':len(rr),'survived':all(x['hit'] for x in rr),'event_ids':'|'.join(x['event_id'] for x in rr)})
    write_csv(OUT/'daily_bundles.csv',bundles);write_csv(OUT/'bundle_failures.csv',[x for x in bundles if not x['survived']])
    nw=len(settled);ww=sum(x['hit'] for x in settled);nd=len(bundles);wd=sum(x['survived'] for x in bundles);ll,_=wilson(ww,nw);dl,_=wilson(wd,nd)
    dist=Counter(x['legs'] for x in bundles);src=Counter(x['source'] for x in settled);team=Counter(x['selected_entity'] for x in settled);month=Counter(x['date'][:7] for x in settled)
    summary={'hypothesis_id':'FOOTBALL_SUMMER_FAVORITE_PLUS1_5_MULTI3_V2_AVGC','validation_year':YEAR,'threshold':TH,'max_per_date':MAX_PER_DATE,'source_audit':audit,'eligible_events_pre_cap':len(pregame),'selected_legs':nw,'leg_wins':ww,'leg_losses':nw-ww,'leg_rate':ww/nw if nw else 0,'leg_wilson95_lcb':ll,'candidate_dates':nd,'bundle_wins':wd,'bundle_losses':nd-wd,'bundle_rate':wd/nd if nd else 0,'bundle_wilson95_lcb':dl,'date_leg_count_distribution':dict(sorted(dist.items())),'source_concentration':dict(src),'max_team':team.most_common(1)[0] if team else None,'max_month':month.most_common(1)[0] if month else None,'duplicates':dups,'candidate_generation_used_outcomes':False,'source_gate_pass':True,'leg_gate_pass':nw>=MIN_N and ll>=MIN_LCB,'bundle_gate_pass':nd>=MIN_N and dl>=MIN_LCB}
    summary['decision']='SCIENCE_CERTAINTY_PASS' if summary['leg_gate_pass'] and summary['bundle_gate_pass'] else 'NO_PASS'
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');(OUT/'source_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
