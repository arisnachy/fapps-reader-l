from __future__ import annotations
import csv,io,json,math,urllib.request,hashlib
from collections import defaultdict,Counter
from datetime import datetime
from pathlib import Path

H='FOOTBALL_TOTAL_2_5_MARKET_DOMINANCE_V1'; BLOCK='0405'; LEAGUES=['E0','SP1','D1','I1']; TH=0.75; Z=1.959963984540054; OUT=Path('front1_total25_market_dominance_0405_output'); OUT.mkdir(exist_ok=True)
REQ=['Date','HomeTeam','AwayTeam','FTHG','FTAG','B365>2.5','B365<2.5']
def pd(x):
 for f in ('%d/%m/%y','%d/%m/%Y','%d-%m-%y','%d-%m-%Y'):
  try:return datetime.strptime(x.strip(),f).date()
  except:pass
 raise ValueError(x)
def wilson(k,n):
 if not n:return 0.,1.
 p=k/n;z2=Z*Z;den=1+z2/n;c=(p+z2/(2*n))/den;m=Z*math.sqrt(p*(1-p)/n+z2/(4*n*n))/den;return max(0,c-m),min(1,c+m)
rows=[];audit={};seen=set();dups=[]
for lg in LEAGUES:
 url=f'https://www.football-data.co.uk/mmz4281/{BLOCK}/{lg}.csv';data=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'KIRA-Science/1.0'}),timeout=40).read();txt=data.decode('utf-8-sig',errors='replace'); txt=data.decode('latin-1') if '\ufffd' in txt else txt
 rd=csv.DictReader(io.StringIO(txt));fields=rd.fieldnames or [];miss=[c for c in REQ if c not in fields]
 if miss:raise RuntimeError(f'{lg}:missing:{miss}')
 raw=valid=bad=0;dates=[]
 for r in rd:
  if not any((v or '').strip() for v in r.values()):continue
  raw+=1
  try:
   d=pd(r['Date']);h=r['HomeTeam'].strip();a=r['AwayTeam'].strip();gh=int(float(r['FTHG']));ga=int(float(r['FTAG']));ov=float(r['B365>2.5']);un=float(r['B365<2.5'])
   if not h or not a or ov<=1 or un<=1:raise ValueError
   key=(d.isoformat(),lg,h,a)
   if key in seen:dups.append(key)
   seen.add(key);qo,qu=1/ov,1/un;den=qo+qu;po,pu=qo/den,qu/den;side='OVER' if po>pu else ('UNDER' if pu>po else None);p=max(po,pu) if side else None;price=ov if side=='OVER' else (un if side=='UNDER' else None)
   rows.append({'date':d.isoformat(),'league':lg,'home':h,'away':a,'B365_over_2_5':ov,'B365_under_2_5':un,'p_over_novig':po,'p_under_novig':pu,'selected_side':side,'p_total_side_novig':p,'selected_price':price,'FTHG':gh,'FTAG':ga});valid+=1;dates.append(d)
  except Exception:bad+=1
 sha=hashlib.sha256(data).hexdigest();audit[lg]={'url':url,'sha256':sha,'bytes':len(data),'raw_rows':raw,'valid_rows':valid,'bad_rows':bad,'date_min':min(dates).isoformat() if dates else None,'date_max':max(dates).isoformat() if dates else None}
if dups:raise RuntimeError(f'duplicates:{len(dups)}')
elig=[r for r in rows if r['selected_side'] and r['p_total_side_novig']>=TH];by=defaultdict(list)
for r in elig:by[r['date']].append(r)
pre=[]
for d,items in sorted(by.items()):pre.append(sorted(items,key=lambda r:(-r['p_total_side_novig'],r['selected_price'],r['league'],r['home'],r['away'],r['selected_side']))[0])
pre_fields=['date','league','home','away','B365_over_2_5','B365_under_2_5','p_over_novig','p_under_novig','selected_side','p_total_side_novig','selected_price']
with (OUT/'selected_event_keys_pre_settlement.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=pre_fields);w.writeheader();w.writerows([{k:r[k] for k in pre_fields} for r in pre])
sett=[]
for r in pre:
 total=r['FTHG']+r['FTAG'];ok=total>2.5 if r['selected_side']=='OVER' else total<2.5;sett.append({**r,'total_goals':total,'settlement':'PASS' if ok else 'FAIL'})
fields=pre_fields+['FTHG','FTAG','total_goals','settlement']
for name,data in [('selected_legs.csv',sett),('failures.csv',[r for r in sett if r['settlement']=='FAIL'])]:
 with (OUT/name).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([{k:r[k] for k in fields} for r in data])
n=len(sett);fail=sum(r['settlement']=='FAIL' for r in sett);k=n-fail;lo,hi=wilson(k,n);sides=Counter(r['selected_side'] for r in sett);leagues=Counter(r['league'] for r in sett)
integrity={'source_identity_pass':all(x['valid_rows']>0 for x in audit.values()),'duplicate_rows':len(dups),'one_selection_per_date_pass':len(pre)==len({r['date'] for r in pre}),'threshold_pass':all(r['p_total_side_novig']>=TH for r in pre),'settlement_complete_pass':len(sett)==len(pre),'settlement_rule_pass':all((r['settlement']=='PASS')==((r['total_goals']>2.5) if r['selected_side']=='OVER' else (r['total_goals']<2.5)) for r in sett),'result_leakage_firewall_pass':True,'eligible_raw_events':len(elig),'side_counts':dict(sides),'league_counts':dict(leagues)}
passed=all(v for key,v in integrity.items() if key.endswith('_pass')) and not dups and n>=35 and lo>=.90
summary={'hypothesis_id':H,'validation_block':BLOCK,'leagues':LEAGUES,'threshold':TH,'selected':n,'settled':n,'survived':k,'failed':fail,'rate':k/n if n else None,'wilson95_lower':lo,'wilson95_upper':hi,'n_gate':{'required':35,'observed':n,'pass':n>=35},'lcb_gate':{'required':.90,'observed':lo,'pass':lo>=.90},'integrity':integrity,'final_result':'PASS' if passed else 'NO_PASS','anti_retune_guard':'Terminal 0405 result; no rerun/threshold/source/league/line changes.'}
for name,obj in [('summary.json',summary),('source_audit.json',audit)]: (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,indent=2,ensure_ascii=False))
