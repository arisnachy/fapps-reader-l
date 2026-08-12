from __future__ import annotations

import csv, hashlib, io, json, math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import requests

OUT=Path('artifacts/kira_euro_lower10_tierb_p055_transport_v1');OUT.mkdir(parents=True,exist_ok=True)
LEAGUES=['E1','E2','E3','SP2','D2','I2','F2','SC1','SC2','SC3']
BLOCKS=[('DEV_2223','2223'),('OOS_2324','2324')]
REQ=['Date','HomeTeam','AwayTeam','AvgCH','AvgCD','AvgCA','FTHG','FTAG']
P_MIN=.55;MAX_DATE=3;GATE=.90;MIN_LEGS=300;MIN_DATES=150

def wilson(w,n,z=1.959963984540054):
    if n<=0:return (0.0,1.0)
    p=w/n;den=1+z*z/n;center=(p+z*z/(2*n))/den;margin=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return max(0,center-margin),min(1,center+margin)

def pdate(v):
    s=str(v or '').strip()
    for fmt in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(s,fmt).date()
        except:pass
    return None

def decode(raw):
    for enc in ('utf-8-sig','latin-1'):
        try:return enc,list(csv.reader(io.StringIO(raw.decode(enc),newline='')))
        except:pass
    raise RuntimeError('CSV_DECODE_FAILED')

def write_csv(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)

def fetch_block(season):
    s=requests.Session();s.headers['User-Agent']='KIRA-EURO-LOWER10-P055-V1/1.0'
    pre=[];outcomes={};audit=[];seen=set()
    for league in LEAGUES:
        url=f'https://www.football-data.co.uk/mmz4281/{season}/{league}.csv'
        try:r=s.get(url,timeout=45);r.raise_for_status();raw=r.content;enc,rows=decode(raw)
        except Exception as exc:
            audit.append({'season':season,'league':league,'status':'SOURCE_UNUSABLE','reason':type(exc).__name__});continue
        sha=hashlib.sha256(raw).hexdigest();header=None;hi=None
        for i,row in enumerate(rows):
            h=[str(x).strip() for x in row]
            if all(c in h for c in REQ):header=h;hi=i;break
        if header is None:
            audit.append({'season':season,'league':league,'status':'SOURCE_UNUSABLE','sha256':sha,'reason':'MISSING_REQUIRED_COLUMNS'});continue
        idx={c:header.index(c) for c in REQ};mx=max(idx.values());eligible=0;valid=0
        for row in rows[hi+1:]:
            if len(row)<=mx:continue
            d=pdate(row[idx['Date']]);home=row[idx['HomeTeam']].strip();away=row[idx['AwayTeam']].strip()
            if d is None or not home or not away:continue
            try:h=float(row[idx['AvgCH']]);dr=float(row[idx['AvgCD']]);a=float(row[idx['AvgCA']]);hg=int(float(row[idx['FTHG']]));ag=int(float(row[idx['FTAG']]))
            except:continue
            if not all(math.isfinite(x) and x>1 for x in (h,dr,a)):continue
            valid+=1;qh,qd,qa=1/h,1/dr,1/a;den=qh+qd+qa;ph,pa=qh/den,qa/den
            if ph==pa:continue
            side='HOME' if ph>pa else 'AWAY';prob=max(ph,pa)
            if prob<P_MIN:continue
            key=(d.isoformat(),league,home,away)
            if key in seen:continue
            seen.add(key);price=h if side=='HOME' else a;ent=home if side=='HOME' else away;eid='EL10-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            pre.append({'date':d.isoformat(),'season':season,'league':league,'Home':home,'Away':away,'selected_side':side,'selected_entity':ent,'selected_price':price,'p_favorite_novig':prob,'event_id':eid})
            outcomes[eid]={'home_goals':hg,'away_goals':ag};eligible+=1
        audit.append({'season':season,'league':league,'status':'PASS','sha256':sha,'encoding':enc,'valid_rows':valid,'eligible_pre_cap':eligible})
    return pre,outcomes,audit

def cap(pre):
    by=defaultdict(list)
    for x in pre:by[x['date']].append(x)
    selected=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(-x['p_favorite_novig'],x['selected_price'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:MAX_DATE]
        for rank,x in enumerate(rr,1):selected.append({**x,'date_rank':rank})
    return selected

def score(label,season):
    bd=OUT/label.lower();bd.mkdir(parents=True,exist_ok=True)
    pre,outcomes,audit=fetch_block(season);source_pass=len(audit)==len(LEAGUES) and all(x.get('status')=='PASS' for x in audit)
    if not source_pass:
        res={'block':label,'season':season,'status':'SOURCE_GATE_FAIL','source_audit':audit};(bd/'summary.json').write_text(json.dumps(res,indent=2));return res
    selected=cap(pre);write_csv(bd/'selected_pre_settlement.csv',selected);sha=hashlib.sha256((bd/'selected_pre_settlement.csv').read_bytes()).hexdigest()
    settled=[]
    for x in selected:
        o=outcomes[x['event_id']];gd=(o['home_goals']-o['away_goals']) if x['selected_side']=='HOME' else (o['away_goals']-o['home_goals']);settled.append({**x,**o,'selected_goal_diff':gd,'hit':gd+1.5>0})
    write_csv(bd/'settled_legs.csv',settled);write_csv(bd/'failures.csv',[x for x in settled if not x['hit']])
    by=defaultdict(list)
    for x in settled:by[x['date']].append(x)
    bundles=[{'date':d,'legs':len(rr),'survived':all(x['hit'] for x in rr),'event_ids':'|'.join(x['event_id'] for x in sorted(rr,key=lambda z:z['date_rank']))} for d,rr in sorted(by.items())]
    write_csv(bd/'daily_bundles.csv',bundles);write_csv(bd/'bundle_failures.csv',[x for x in bundles if not x['survived']])
    nl=len(settled);wl=sum(x['hit'] for x in settled);nd=len(bundles);wd=sum(x['survived'] for x in bundles);ll,lu=wilson(wl,nl);dl,du=wilson(wd,nd);lr=wl/nl if nl else 0;dr=wd/nd if nd else 0
    outcome_blind=True;dup=nl-len({x['event_id'] for x in settled})
    gates={'source_gate':source_pass,'legs_n_ge_300':nl>=MIN_LEGS,'dates_n_ge_150':nd>=MIN_DATES,'leg_rate_gt_90':lr>GATE,'leg_wilson_lcb_gt_90':ll>GATE,'bundle_rate_gt_90':dr>GATE,'bundle_wilson_lcb_gt_90':dl>GATE,'candidate_generation_outcome_blind':outcome_blind,'duplicate_event_keys_zero':dup==0,'max3_per_date':all(x['legs']<=MAX_DATE for x in bundles),'settlement_complete':len(settled)==nl}
    passed=all(gates.values())
    res={'hypothesis_id':'FOOTBALL_EURO_LOWER10_TIERB_P055_TRANSPORT_V1','block':label,'season':season,'status':'PASS' if passed else 'NO_PASS','eligible_pre_cap':len(pre),'selected_legs':nl,'leg_wins':wl,'leg_losses':nl-wl,'leg_rate':lr,'leg_wilson95_lcb':ll,'leg_wilson95_ucb':lu,'candidate_dates':nd,'bundle_wins':wd,'bundle_losses':nd-wd,'bundle_rate':dr,'bundle_wilson95_lcb':dl,'bundle_wilson95_ucb':du,'date_leg_count_distribution':dict(sorted(Counter(x['legs'] for x in bundles).items())),'selected_ledger_sha256':sha,'duplicate_event_keys':dup,'gates':gates,'source_audit':audit,'frozen_contract':{'p_min':P_MIN,'line':'+1.5','max_per_date':MAX_DATE,'leagues':LEAGUES}}
    (bd/'summary.json').write_text(json.dumps(res,indent=2));return res

def main():
    overall={'hypothesis_id':'FOOTBALL_EURO_LOWER10_TIERB_P055_TRANSPORT_V1','preregistration':'prereg/FOOTBALL_EURO_LOWER10_TIERB_P055_TRANSPORT_V1_2026-08-12.md','blocks':[],'oos_opened':False}
    dev=score(*BLOCKS[0]);overall['blocks'].append(dev)
    if dev.get('status')!='PASS':overall['decision']='DEV_NO_PASS_CLOSED_OOS_UNOPENED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2));return
    overall['oos_opened']=True;oos=score(*BLOCKS[1]);overall['blocks'].append(oos);overall['decision']='OOS_TRANSPORT_PASS' if oos.get('status')=='PASS' else 'OOS_NO_PASS_CLOSED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2))
if __name__=='__main__':main()
