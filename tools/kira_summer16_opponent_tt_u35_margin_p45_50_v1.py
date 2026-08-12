from __future__ import annotations
import csv,hashlib,io,json,math
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
import requests

OUT=Path('artifacts/kira_summer16_opponent_tt_u35_margin_p45_50_v1');OUT.mkdir(parents=True,exist_ok=True)
CODES=['ARG','AUT','BRA','CHN','DNK','FIN','IRL','JPN','MEX','NOR','POL','ROU','RUS','SWE','SWZ','USA']
BLOCKS=[('DEV_2013',2013),('OOS_2014',2014)];REQ=['Date','Home','Away','League','AvgCH','AvgCD','AvgCA','HG','AG'];LOW=.45;HIGH=.50;MAXD=3

def wilson(w,n,z=1.959963984540054):
    if not n:return 0.,1.
    p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d;return max(0,c-m),min(1,c+m)
def pdate(v):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:return datetime.strptime(str(v).strip(),f).date()
        except:pass
    return None
def write(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fs=[]
    for r in rows:
        for k in r:
            if k not in fs:fs.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:w=csv.DictWriter(fh,fieldnames=fs);w.writeheader();w.writerows(rows)
def fetch_year(year):
    s=requests.Session();s.headers['User-Agent']='KIRA-SUMMER16-U35-P45-50/1.0';pre=[];out={};audit=[];seen=set()
    for code in CODES:
        url=f'https://www.football-data.co.uk/new/{code}.csv'
        try:r=s.get(url,timeout=60);r.raise_for_status();raw=r.content;rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))))
        except Exception as exc:audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':type(exc).__name__});continue
        if not rows:audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':'EMPTY'});continue
        h=[x.strip() for x in rows[0]];miss=[c for c in REQ if c not in h]
        if miss:audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':'MISSING_COLUMNS','missing':miss});continue
        ix={c:h.index(c) for c in REQ};mx=max(ix.values());serial=[];eligible=0
        for row in rows[1:]:
            if len(row)<=mx:continue
            d=pdate(row[ix['Date']])
            if d is None or d.year!=year:continue
            serial.append(','.join(row));home=row[ix['Home']].strip();away=row[ix['Away']].strip();lg=row[ix['League']].strip()
            try:h=float(row[ix['AvgCH']]);dr=float(row[ix['AvgCD']]);a=float(row[ix['AvgCA']]);hg=int(float(row[ix['HG']]));ag=int(float(row[ix['AG']]))
            except:continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h,dr,a)):continue
            qh,qd,qa=1/h,1/dr,1/a;den=qh+qd+qa;ph,pa=qh/den,qa/den
            if ph==pa:continue
            side='HOME' if ph>pa else 'AWAY';prob=max(ph,pa)
            if not (LOW<=prob<HIGH):continue
            key=(d.isoformat(),code,lg,home,away)
            if key in seen:continue
            seen.add(key);sel=home if side=='HOME' else away;opp=away if side=='HOME' else home;price=h if side=='HOME' else a;eid='S16M45-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            pre.append({'date':d.isoformat(),'source':code,'league':lg,'Home':home,'Away':away,'selected_side':side,'selected_entity':sel,'opponent_entity':opp,'selected_price':price,'p_selected_novig':prob,'event_id':eid});out[eid]={'HG':hg,'AG':ag};eligible+=1
        audit.append({'source':code,'status':'PASS' if serial else 'SOURCE_UNUSABLE','reason':'' if serial else 'NO_TARGET_YEAR_ROWS','file_sha256':hashlib.sha256(raw).hexdigest(),'target_rows':len(serial),'target_rows_sha256':hashlib.sha256('\n'.join(serial).encode()).hexdigest(),'eligible_band_pre_cap':eligible})
    return pre,out,audit
def score(label,year):
    bd=OUT/label.lower();bd.mkdir(parents=True,exist_ok=True);pre,out,audit=fetch_year(year);source_ok=len(audit)==len(CODES) and all(x.get('status')=='PASS' for x in audit)
    if not source_ok:
        r={'block':label,'year':year,'status':'SOURCE_GATE_FAIL','source_audit':audit};(bd/'summary.json').write_text(json.dumps(r,indent=2));return r
    by=defaultdict(list)
    for x in pre:by[x['date']].append(x)
    sel=[]
    for d,rr in sorted(by.items()):
        rr=sorted(rr,key=lambda x:(-x['p_selected_novig'],x['selected_price'],x['source'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))[:MAXD]
        for rank,x in enumerate(rr,1):sel.append({**x,'date_rank':rank})
    write(bd/'selected_pre_settlement.csv',sel);sha=hashlib.sha256((bd/'selected_pre_settlement.csv').read_bytes()).hexdigest();settled=[]
    for x in sel:
        o=out[x['event_id']];opp_goals=o['AG'] if x['selected_side']=='HOME' else o['HG'];settled.append({**x,**o,'opponent_goals':opp_goals,'hit':opp_goals<=3})
    write(bd/'settled_legs.csv',settled);write(bd/'failures.csv',[x for x in settled if not x['hit']]);byd=defaultdict(list)
    for x in settled:byd[x['date']].append(x)
    bundles=[{'date':d,'legs':len(rr),'survived':all(x['hit'] for x in rr)} for d,rr in sorted(byd.items())];write(bd/'daily_bundles.csv',bundles)
    nl=len(settled);wl=sum(x['hit'] for x in settled);nd=len(bundles);wd=sum(x['survived'] for x in bundles);lr=wl/nl if nl else 0;dr=wd/nd if nd else 0;ll,_=wilson(wl,nl);dl,_=wilson(wd,nd)
    gates={'all16_sources_pass':source_ok,'legs_ge_250':nl>=250,'dates_ge_120':nd>=120,'leg_rate_gt_90':lr>.90,'bundle_rate_gt_90':dr>.90,'outcome_blind':True,'unique_events':len({x['event_id'] for x in settled})==nl,'max3_date':all(x['legs']<=3 for x in bundles),'settlement_complete':len(settled)==nl}
    r={'hypothesis_id':'FOOTBALL_SUMMER16_OPPONENT_TT_U35_MARGIN_P45_50_V1','block':label,'year':year,'status':'PASS' if all(gates.values()) else 'NO_PASS','selected_legs':nl,'leg_wins':wl,'leg_rate':lr,'leg_wilson95_lcb':ll,'candidate_dates':nd,'bundle_wins':wd,'bundle_rate':dr,'bundle_wilson95_lcb':dl,'date_leg_count_distribution':dict(sorted(Counter(x['legs'] for x in bundles).items())),'selected_ledger_sha256':sha,'gates':gates,'source_audit':audit};(bd/'summary.json').write_text(json.dumps(r,indent=2));return r
def main():
    overall={'hypothesis_id':'FOOTBALL_SUMMER16_OPPONENT_TT_U35_MARGIN_P45_50_V1','blocks':[],'oos_opened':False};dev=score(*BLOCKS[0]);overall['blocks'].append(dev)
    if dev.get('status')!='PASS':overall['decision']='DEV_NO_PASS_CLOSED_OOS_UNOPENED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2));return
    overall['oos_opened']=True;oos=score(*BLOCKS[1]);overall['blocks'].append(oos);overall['decision']='OOS_CERTAINTY_PASS' if oos.get('status')=='PASS' else 'OOS_NO_PASS_CLOSED';(OUT/'overall_summary.json').write_text(json.dumps(overall,indent=2));print(json.dumps(overall,indent=2))
if __name__=='__main__':main()
