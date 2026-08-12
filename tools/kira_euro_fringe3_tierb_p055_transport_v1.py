from __future__ import annotations
import csv,hashlib,io,json,math
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
import requests
OUT=Path('artifacts/kira_euro_fringe3_tierb_p055_transport_v1');OUT.mkdir(parents=True,exist_ok=True)
LEAGUES=['T1','G1','EC'];BLOCKS=[('DEV_2223','2223'),('OOS_2324','2324')]
REQ=['Date','HomeTeam','AwayTeam','AvgCH','AvgCD','AvgCA','FTHG','FTAG'];P=.55;MAXD=3

def wilson(w,n,z=1.959963984540054):
    if not n:return 0.0,1.0
    p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d;return max(0,c-m),min(1,c+m)
def pdate(v):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(v).strip(),f).date()
        except:pass
    return None
def decode(raw):
    for enc in ('utf-8-sig','latin-1'):
        try:return enc,list(csv.reader(io.StringIO(raw.decode(enc),newline='')))
        except:pass
    raise RuntimeError('DECODE')
def write_csv(path,rows):
    if not rows:path.write_text('');return
    fs=[]
    for r in rows:
        for k in r:
            if k not in fs:fs.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:w=csv.DictWriter(fh,fieldnames=fs);w.writeheader();w.writerows(rows)
def fetch(season):
    s=requests.Session();s.headers['User-Agent']='KIRA-FRINGE3-P055-V1/1.0';pre=[];out={};audit=[]
    for lg in LEAGUES:
        url=f'https://www.football-data.co.uk/mmz4281/{season}/{lg}.csv'
        try:
            r=s.get(url,timeout=45)
            if r.status_code==404:audit.append({'season':season,'league':lg,'status':'SOURCE_ABSENT','http':404});continue
            r.raise_for_status();raw=r.content;enc,rows=decode(raw)
        except Exception as exc:audit.append({'season':season,'league':lg,'status':'SOURCE_UNUSABLE','reason':type(exc).__name__});continue
        sha=hashlib.sha256(raw).hexdigest();header=None;hi=None
        for i,row in enumerate(rows):
            h=[str(x).strip() for x in row]
            if all(c in h for c in REQ):header=h;hi=i;break
        if header is None:audit.append({'season':season,'league':lg,'status':'SOURCE_UNUSABLE','sha256':sha,'reason':'MISSING_COLUMNS'});continue
        ix={c:header.index(c) for c in REQ};mx=max(ix.values());n=0
        for row in rows[hi+1:]:
            if len(row)<=mx:continue
            d=pdate(row[ix['Date']]);home=row[ix['HomeTeam']].strip();away=row[ix['AwayTeam']].strip()
            try:h=float(row[ix['AvgCH']]);dr=float(row[ix['AvgCD']]);a=float(row[ix['AvgCA']]);hg=int(float(row[ix['FTHG']]));ag=int(float(row[ix['FTAG']]))
            except:continue
            if d is None or not home or not away or not all(math.isfinite(x) and x>1 for x in (h,dr,a)):continue
            qh,qd,qa=1/h,1/dr,1/a;den=qh+qd+qa;ph,pa=qh/den,qa/den
            if ph==pa:continue
            side='HOME' if ph>pa else 'AWAY';prob=max(ph,pa)
            if prob<P:continue
            ent=home if side=='HOME' else away;price=h if side=='HOME' else a;key=f'{season}|{lg}|{d.isoformat()}|{home}|{away}';eid='EF3-'+hashlib.sha256(key.encode()).hexdigest()[:20]
            pre.append({'date':d.isoformat(),'season':season,'league':lg,'Home':home,'Away':away,'selected_side':side,'selected_entity':ent,'selected_price':price,'p_favorite_novig':prob,'event_id':eid});out[eid]={'home_goals':hg,'away_goals':ag};n+=1
        audit.append({'season':season,'league':lg,'status':'PASS','sha256':sha,'encoding':enc,'eligible_pre_cap':n})
    return pre,out,audit
def score(label,season):
    bd=OUT/label.lower();bd.mkdir(parents=True,exist_ok=True);pre,out,audit=fetch(season);usable=[x for x in audit if x.get('status')=='PASS'];bad=[x for x in audit if x.get('status')=='SOURCE_UNUSABLE']
    if len(usable)<2 or bad:
        r={'block':label,'season':season,'status':'SOURCE_GATE_FAIL','source_audit':audit};(bd/'summary.json').write_text(json.dumps(r,indent=2));return r
    by=defaultdict(list)
    for x in pre:by[x['date']].append(x)
    sel=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(-x['p_favorite_novig'],x['selected_price'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:MAXD]
        for rank,x in enumerate(rr,1):sel.append({**x,'date_rank':rank})
    write_csv(bd/'selected_pre_settlement.csv',sel);sha=hashlib.sha256((bd/'selected_pre_settlement.csv').read_bytes()).hexdigest();settled=[]
    for x in sel:
        o=out[x['event_id']];gd=(o['home_goals']-o['away_goals']) if x['selected_side']=='HOME' else (o['away_goals']-o['home_goals']);settled.append({**x,**o,'selected_goal_diff':gd,'hit':gd+1.5>0})
    write_csv(bd/'settled.csv',settled);byd=defaultdict(list)
    for x in settled:byd[x['date']].append(x)
    bundles=[{'date':d,'legs':len(rr),'survived':all(x['hit'] for x in rr)} for d,rr in sorted(byd.items())];write_csv(bd/'bundles.csv',bundles)
    nl=len(settled);wl=sum(x['hit'] for x in settled);nd=len(bundles);wd=sum(x['survived'] for x in bundles);ll,_=wilson(wl,nl);dl,_=wilson(wd,nd);lr=wl/nl if nl else 0;dr=wd/nd if nd else 0
    gates={'usable_leagues_ge_2':len(usable)>=2,'no_source_unusable':not bad,'legs_ge_100':nl>=100,'dates_ge_60':nd>=60,'leg_rate_gt_90':lr>.90,'bundle_rate_gt_90':dr>.90,'outcome_blind':True,'unique_events':len({x['event_id'] for x in settled})==nl,'max3_date':all(x['legs']<=3 for x in bundles)}
    r={'hypothesis_id':'FOOTBALL_EURO_FRINGE3_TIERB_P055_TRANSPORT_V1','block':label,'season':season,'status':'PASS' if all(gates.values()) else 'NO_PASS','selected_legs':nl,'leg_wins':wl,'leg_rate':lr,'leg_wilson95_lcb':ll,'candidate_dates':nd,'bundle_wins':wd,'bundle_rate':dr,'bundle_wilson95_lcb':dl,'date_leg_count_distribution':dict(sorted(Counter(x['legs'] for x in bundles).items())),'selected_ledger_sha256':sha,'gates':gates,'source_audit':audit};(bd/'summary.json').write_text(json.dumps(r,indent=2));return r
def main():
    overall={'hypothesis_id':'FOOTBALL_EURO_FRINGE3_TIERB_P055_TRANSPORT_V1','blocks':[],'oos_opened':False};dev=score(*BLOCKS[0]);overall['blocks'].append(dev)
    if dev.get('status')!='PASS':overall['decision']='DEV_NO_PASS_CLOSED_OOS_UNOPENED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2));return
    overall['oos_opened']=True;oos=score(*BLOCKS[1]);overall['blocks'].append(oos);overall['decision']='OOS_TRANSPORT_PASS' if oos.get('status')=='PASS' else 'OOS_NO_PASS_CLOSED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2))
if __name__=='__main__':main()
