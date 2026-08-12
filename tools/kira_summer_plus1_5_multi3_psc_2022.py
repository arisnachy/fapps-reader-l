from __future__ import annotations
import csv,io,json,hashlib,math
from collections import Counter
from datetime import datetime
from pathlib import Path
import requests
OUT=Path('artifacts/kira_summer_plus1_5_multi3_psc_2022');OUT.mkdir(parents=True,exist_ok=True)
SOURCES={'BRA':'https://www.football-data.co.uk/new/BRA.csv','USA':'https://www.football-data.co.uk/new/USA.csv'}
REQ=['Date','Home','Away','League','PSCH','PSCD','PSCA','HG','AG']
YEAR=2022;TH=.60;MIN_N=35;MIN_LCB=.92

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
    s=requests.Session();s.headers['User-Agent']='KIRA-SUMMER-PSC22/1.0';pre=[];outcomes={};audit=[];seen=set();dups=0
    for code,url in SOURCES.items():
        r=s.get(url,timeout=60);r.raise_for_status();raw=r.content;rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))));h=[x.strip() for x in rows[0]]
        if not all(c in h for c in REQ):audit.append({'source':code,'status':'MISSING_COLUMNS'});continue
        idx={c:h.index(c) for c in REQ};mx=max(idx.values());serial=[];n=0
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']]);
            if d is None or d.year!=YEAR:continue
            serial.append(','.join(row));home=row[idx['Home']].strip();away=row[idx['Away']].strip();lg=row[idx['League']].strip()
            try:h1=float(row[idx['PSCH']]);dr=float(row[idx['PSCD']]);a1=float(row[idx['PSCA']]);hg=int(float(row[idx['HG']]));ag=int(float(row[idx['AG']]))
            except:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h1,dr,a1)):continue
            qh,qd,qa=1/h1,1/dr,1/a1;den=qh+qd+qa;ph,pa=qh/den,qa/den
            if ph==pa:continue
            side='HOME' if ph>pa else 'AWAY';prob=max(ph,pa)
            if prob<TH:continue
            price=h1 if side=='HOME' else a1;ent=home if side=='HOME' else away;key=(d.isoformat(),code,lg,home,away)
            if key in seen:dups+=1;continue
            seen.add(key);eid='PSC22-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            pre.append({'date':d.isoformat(),'source':code,'league':lg,'Home':home,'Away':away,'selected_side':side,'selected_entity':ent,'selected_price':price,'p_favorite_novig':prob,'event_id':eid});outcomes[eid]={'HG':hg,'AG':ag};n+=1
        audit.append({'source':code,'status':'PASS','file_sha256':hashlib.sha256(raw).hexdigest(),'target_rows_sha256':hashlib.sha256('\n'.join(serial).encode()).hexdigest(),'target_rows':len(serial),'eligible_pre_cap':n})
    if any(x.get('status')!='PASS' for x in audit):
        res={'decision':'SOURCE_GATE_FAIL','source_audit':audit};(OUT/'summary.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2));return
    if dups:raise SystemExit(f'DUPS={dups}')
    by={}
    for x in pre:by.setdefault(x['date'],[]).append(x)
    selected=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(-x['p_favorite_novig'],x['selected_price'],x['source'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:3]
        for rank,x in enumerate(rr,1):selected.append({**x,'date_rank':rank})
    write(OUT/'selected_event_keys_pre_settlement.csv',selected)
    settled=[]
    for x in selected:
        o=outcomes[x['event_id']];gd=(o['HG']-o['AG']) if x['selected_side']=='HOME' else (o['AG']-o['HG']);settled.append({**x,**o,'selected_goal_diff':gd,'hit':gd+1.5>0})
    write(OUT/'selected_legs.csv',settled);write(OUT/'failures.csv',[x for x in settled if not x['hit']])
    dates={}
    for x in settled:dates.setdefault(x['date'],[]).append(x)
    bundles=[{'date':d,'legs':len(rr),'survived':all(x['hit'] for x in rr),'event_ids':'|'.join(x['event_id'] for x in rr)} for d,rr in sorted(dates.items())]
    write(OUT/'daily_bundles.csv',bundles);write(OUT/'bundle_failures.csv',[x for x in bundles if not x['survived']])
    nl=len(settled);wl=sum(x['hit'] for x in settled);nd=len(bundles);wd=sum(x['survived'] for x in bundles);ll,_=wilson(wl,nl);dl,_=wilson(wd,nd)
    res={'hypothesis_id':'FOOTBALL_SUMMER_PLUS1_5_MULTI3_PSC_2022_SOURCE_TRANSFER','selected_legs':nl,'leg_wins':wl,'leg_losses':nl-wl,'leg_rate':wl/nl if nl else 0,'leg_wilson95_lcb':ll,'candidate_dates':nd,'bundle_wins':wd,'bundle_losses':nd-wd,'bundle_rate':wd/nd if nd else 0,'bundle_wilson95_lcb':dl,'date_leg_count_distribution':dict(sorted(Counter(x['legs'] for x in bundles).items())),'source_audit':audit,'candidate_generation_used_outcomes':False,'duplicate_event_keys':dups,'leg_gate_pass':nl>=MIN_N and ll>=MIN_LCB,'bundle_gate_pass':nd>=MIN_N and dl>=MIN_LCB}
    res['decision']='SOURCE_TRANSFER_PASS' if res['leg_gate_pass'] and res['bundle_gate_pass'] else 'NO_PASS';(OUT/'summary.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
if __name__=='__main__':main()
