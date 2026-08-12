from __future__ import annotations
import csv,io,json,hashlib,math
from collections import Counter
from datetime import datetime
from pathlib import Path
import requests
OUT=Path('artifacts/kira_extra16_favorite_plus1_5_multi3_2021');OUT.mkdir(parents=True,exist_ok=True)
CODES=['ARG','AUT','BRA','CHN','DNK','FIN','IRL','JPN','MEX','NOR','POL','ROU','RUS','SWE','SWZ','USA']
REQ=['Date','Home','Away','League','AvgCH','AvgCD','AvgCA','HG','AG']
YEAR=2021;TH=.60;MAX3=3;MIN_LEGS=300;MIN_DATES=200;MIN_LCB=.92

def wilson(w,n,z=1.959963984540054):
    if n<=0:return 0.0,1.0
    p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
    return max(0,c-m),min(1,c+m)
def pdate(s):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(s).strip(),f).date()
        except:pass
    return None
def write(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
    sess=requests.Session();sess.headers['User-Agent']='KIRA-EXTRA16-FAV15-M3-2021/1.0'
    audit=[];pre=[];outcomes={};seen=set();dups=0
    for code in CODES:
        url=f'https://www.football-data.co.uk/new/{code}.csv'
        try:r=sess.get(url,timeout=60);r.raise_for_status()
        except Exception as exc:
            audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':type(exc).__name__});continue
        raw=r.content;rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))))
        if not rows:
            audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':'EMPTY'});continue
        h=[x.strip() for x in rows[0]];miss=[c for c in REQ if c not in h]
        if miss:
            audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':'MISSING_COLUMNS','missing':miss});continue
        idx={c:h.index(c) for c in REQ};mx=max(idx.values());serial=[];eligible=0
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']])
            if d is None or d.year!=YEAR:continue
            serial.append(','.join(row))
            home=row[idx['Home']].strip();away=row[idx['Away']].strip();league=row[idx['League']].strip()
            try:h1=float(row[idx['AvgCH']]);dr=float(row[idx['AvgCD']]);a1=float(row[idx['AvgCA']]);hg=int(float(row[idx['HG']]));ag=int(float(row[idx['AG']]))
            except:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h1,dr,a1)):continue
            qh,qd,qa=1/h1,1/dr,1/a1;den=qh+qd+qa;ph,pa=qh/den,qa/den
            if ph==pa:continue
            side='HOME' if ph>pa else 'AWAY';prob=max(ph,pa)
            if prob<TH:continue
            price=h1 if side=='HOME' else a1;ent=home if side=='HOME' else away
            key=(d.isoformat(),code,league,home,away)
            if key in seen:dups+=1;continue
            seen.add(key);eid='X16-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            pre.append({'date':d.isoformat(),'source':code,'league':league,'Home':home,'Away':away,'selected_side':side,'selected_entity':ent,'selected_price':price,'p_favorite_novig':prob,'event_id':eid})
            outcomes[eid]={'HG':hg,'AG':ag};eligible+=1
        audit.append({'source':code,'status':'PASS','file_sha256':hashlib.sha256(raw).hexdigest(),'target_rows_sha256':hashlib.sha256('\n'.join(serial).encode()).hexdigest(),'target_rows':len(serial),'eligible_pre_cap':eligible})
    if len(audit)!=len(CODES) or any(x.get('status')!='PASS' for x in audit):
        res={'decision':'SOURCE_GATE_FAIL','source_audit':audit};(OUT/'summary.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2));return
    if dups:raise SystemExit(f'DUPLICATES={dups}')
    by={}
    for x in pre:by.setdefault(x['date'],[]).append(x)
    selected=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(-x['p_favorite_novig'],x['selected_price'],x['source'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:MAX3]
        for rank,x in enumerate(rr,1):selected.append({**x,'date_rank':rank})
    # Pre-settlement immutable ledger.
    write(OUT/'selected_event_keys_pre_settlement.csv',selected)
    ledger_sha=hashlib.sha256((OUT/'selected_event_keys_pre_settlement.csv').read_bytes()).hexdigest()
    settled=[]
    for x in selected:
        o=outcomes[x['event_id']];gd=(o['HG']-o['AG']) if x['selected_side']=='HOME' else (o['AG']-o['HG']);settled.append({**x,**o,'selected_goal_diff':gd,'hit':gd+1.5>0})
    write(OUT/'selected_legs.csv',settled);write(OUT/'failures.csv',[x for x in settled if not x['hit']])
    dates={}
    for x in settled:dates.setdefault(x['date'],[]).append(x)
    bundles=[]
    for d,rr in sorted(dates.items()):bundles.append({'date':d,'legs':len(rr),'survived':all(x['hit'] for x in rr),'event_ids':'|'.join(x['event_id'] for x in rr)})
    write(OUT/'daily_bundles.csv',bundles);write(OUT/'bundle_failures.csv',[x for x in bundles if not x['survived']])
    nl=len(settled);wl=sum(x['hit'] for x in settled);nd=len(bundles);wd=sum(x['survived'] for x in bundles);ll,_=wilson(wl,nl);dl,_=wilson(wd,nd)
    src=Counter(x['source'] for x in settled);failsrc=Counter(x['source'] for x in settled if not x['hit']);team=Counter(x['selected_entity'] for x in settled);month=Counter(x['date'][:7] for x in settled);dist=Counter(x['legs'] for x in bundles)
    res={'hypothesis_id':'FOOTBALL_EXTRA16_FAVORITE_PLUS1_5_MULTI3_V1_2021','selected_legs':nl,'leg_wins':wl,'leg_losses':nl-wl,'leg_rate':wl/nl if nl else 0,'leg_wilson95_lcb':ll,'candidate_dates':nd,'bundle_wins':wd,'bundle_losses':nd-wd,'bundle_rate':wd/nd if nd else 0,'bundle_wilson95_lcb':dl,'date_leg_count_distribution':dict(sorted(dist.items())),'source_selected_counts':dict(sorted(src.items())),'failure_source_counts':dict(sorted(failsrc.items())),'max_team':team.most_common(1)[0] if team else None,'max_month':month.most_common(1)[0] if month else None,'source_audit':audit,'selected_ledger_sha256':ledger_sha,'duplicate_event_keys':dups,'candidate_generation_used_outcomes':False,'leg_gate_pass':nl>=MIN_LEGS and ll>=MIN_LCB,'bundle_gate_pass':nd>=MIN_DATES and dl>=MIN_LCB}
    res['decision']='SCIENCE_CERTAINTY_PASS' if res['leg_gate_pass'] and res['bundle_gate_pass'] else 'NO_PASS'
    (OUT/'summary.json').write_text(json.dumps(res,indent=2));(OUT/'source_audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps(res,indent=2))
if __name__=='__main__':main()
