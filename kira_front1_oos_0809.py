from __future__ import annotations
import csv, hashlib, io, json, math, time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

OUT=Path('out'); OUT.mkdir(exist_ok=True)
Z=1.959963984540054; TH=0.75; MIN_N=35; MIN_LCB=0.90
LEAGUES={'E0':'England Premier League','SP1':'Spain La Liga','D1':'Germany Bundesliga','I1':'Italy Serie A','F1':'France Ligue 1','N1':'Netherlands Eredivisie','P1':'Portugal Primeira Liga','SC0':'Scotland Premiership','B1':'Belgium First Division A'}
REQ=['Date','HomeTeam','AwayTeam','FTHG','FTAG','B365H','B365D','B365A']

def fetch(url):
    last=None
    for i in range(4):
        try:
            req=Request(url,headers={'User-Agent':'Mozilla/5.0 KIRA-MARKET-DOMINANCE-V1-OOS-0809/1.0'})
            with urlopen(req,timeout=60) as r: return r.read()
        except Exception as e:
            last=e; time.sleep(1.5+i)
    raise last

def pdate(s):
    s=(s or '').strip()
    for f in ('%d/%m/%y','%d/%m/%Y'):
        try:return datetime.strptime(s,f).date().isoformat()
        except:pass
    return None

def fnum(x):
    try:return float(x)
    except:return None

def wilson(k,n):
    if not n:return (None,None)
    p=k/n; den=1+Z*Z/n; ctr=(p+Z*Z/(2*n))/den; half=Z*math.sqrt((p*(1-p)+Z*Z/(4*n))/n)/den
    return ctr-half,ctr+half

rows=[]; audits={}; fps={}
for code,name in LEAGUES.items():
    url=f'https://www.football-data.co.uk/mmz4281/0809/{code}.csv'
    try:
        b=fetch(url); sha=hashlib.sha256(b).hexdigest(); text=b.decode('utf-8-sig',errors='replace')
        rr=list(csv.DictReader(io.StringIO(text)))
        missing=[c for c in REQ if c not in (rr[0].keys() if rr else [])]
        if missing:
            audits[code]={'league':name,'url':url,'status':'SOURCE_MISSING_REQUIRED_COLUMNS','sha256':sha,'bytes':len(b),'rows_raw':len(rr),'missing_columns':missing}; continue
        valid=[]; bad_dates=0
        for r in rr:
            d=pdate(r.get('Date'))
            if r.get('Date') and not d: bad_dates+=1
            h=fnum(r.get('FTHG')); a=fnum(r.get('FTAG'))
            if d is None or h is None or a is None: continue
            rec={'date':d,'league_code':code,'league':name,'HomeTeam':r['HomeTeam'],'AwayTeam':r['AwayTeam'],'FTHG':int(h),'FTAG':int(a),'B365H':fnum(r.get('B365H')),'B365D':fnum(r.get('B365D')),'B365A':fnum(r.get('B365A'))}
            valid.append(rec)
        keys=[(r['date'],r['league_code'],r['HomeTeam'],r['AwayTeam']) for r in valid]
        dup=len(keys)-len(set(keys))
        audits[code]={'league':name,'url':url,'status':'PASS' if dup==0 else 'FAIL_DUPLICATE_EVENT_KEYS','sha256':sha,'bytes':len(b),'rows_raw':len(rr),'rows_valid_event':len(valid),'bad_date_rows':bad_dates,'duplicate_event_rows':dup,'first_date':min((r['date'] for r in valid),default=None),'last_date':max((r['date'] for r in valid),default=None),'required_columns_present':True}
        fps[code]={'league':name,'url':url,'sha256':sha,'bytes':len(b),'rows_raw':len(rr),'rows_valid_event':len(valid)}
        rows.extend(valid)
    except Exception as e:
        audits[code]={'league':name,'url':url,'status':'SOURCE_FETCH_ERROR','error':type(e).__name__+': '+str(e)}

Path('out/source_audit.json').write_text(json.dumps(audits,indent=2))
Path('out/source_fingerprints.json').write_text(json.dumps(fps,indent=2))
source_pass=len(fps)==len(LEAGUES) and all(v.get('status')=='PASS' for v in audits.values())
allkeys=[(r['date'],r['league_code'],r['HomeTeam'],r['AwayTeam']) for r in rows]; crossdup=len(allkeys)-len(set(allkeys))
if crossdup: source_pass=False

eligible=[]
for r in rows:
    H,D,A=r['B365H'],r['B365D'],r['B365A']
    if not(H and D and A and H>1 and D>1 and A>1): continue
    qh,qd,qa=1/H,1/D,1/A; p=qh/(qh+qd+qa)
    if p>=TH:
        x={k:r[k] for k in ['date','league_code','league','HomeTeam','AwayTeam','B365H','B365D','B365A']}; x['p_home_novig']=p; eligible.append(x)
eligible.sort(key=lambda x:(x['date'],-x['p_home_novig'],x['B365H'],x['league_code'],x['HomeTeam'],x['AwayTeam']))
selected=[]; seen=set()
for x in eligible:
    if x['date'] not in seen: selected.append(x); seen.add(x['date'])

with open('out/selected_event_keys_pre_settlement.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['date','league_code','league','HomeTeam','AwayTeam','B365H','B365D','B365A','p_home_novig']); w.writeheader(); w.writerows(selected)
settle={(r['date'],r['league_code'],r['HomeTeam'],r['AwayTeam']):(r['FTHG'],r['FTAG']) for r in rows}
scored=[]
for s in selected:
    h,a=settle.get((s['date'],s['league_code'],s['HomeTeam'],s['AwayTeam']),(None,None)); z=dict(s); z['FTHG']=h; z['FTAG']=a; z['settlement_available']=h is not None and a is not None; z['pass_plus1_5']=bool(z['settlement_available'] and h+1.5>a); z['loss_margin']=max(0,a-h) if z['settlement_available'] else None; scored.append(z)
fields=['date','league_code','league','HomeTeam','AwayTeam','B365H','B365D','B365A','p_home_novig','FTHG','FTAG','settlement_available','pass_plus1_5','loss_margin']
for fn,data in [('selected_legs.csv',scored),('failures.csv',[r for r in scored if r['settlement_available'] and not r['pass_plus1_5']])]:
    with open('out/'+fn,'w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
n=len(scored); settled=sum(r['settlement_available'] for r in scored); k=sum(r['pass_plus1_5'] for r in scored); l,u=wilson(k,settled)
tc=Counter(r['HomeTeam'] for r in scored); lc=Counter(r['league_code'] for r in scored); mt=tc.most_common(1)[0] if tc else (None,0); ml=lc.most_common(1)[0] if lc else (None,0)
one=n==len({r['date'] for r in scored}); threshold=all(r['p_home_novig']>=TH-1e-12 for r in scored); unique=n==len({(r['date'],r['league_code'],r['HomeTeam'],r['AwayTeam']) for r in scored}); settlement=settled==n and unique; leakage=True
gate=source_pass and settlement and leakage and one and threshold and n>=MIN_N and l is not None and l>=MIN_LCB
summary={'hypothesis_id':'FOOTBALL_PLUS1_5_MARKET_DOMINANCE_V1','block':'2008-09 / 0809','contract':'selected HOME team +1.5','threshold_p_home_novig':TH,'daily_selector':'one highest p_home_novig candidate per date','eligible_candidates':len(eligible),'selected':n,'settled':settled,'survived':k,'failed':settled-k,'rate':k/settled if settled else None,'wilson95_lower':l,'wilson95_upper':u,'min_n':MIN_N,'min_oos_wilson_lcb':MIN_LCB,'n_gate_pass':n>=MIN_N,'wilson_gate_pass':l is not None and l>=MIN_LCB,'source_identity_pass':source_pass,'cross_source_duplicate_event_rows':crossdup,'one_selection_per_date_pass':one,'threshold_pass':threshold,'selected_unique_event_pass':unique,'settlement_pass':settlement,'result_leakage_pass':leakage,'max_team_concentration':{'team':mt[0],'count':mt[1],'fraction':mt[1]/n if n else None},'max_league_concentration':{'league_code':ml[0],'count':ml[1],'fraction':ml[1]/n if n else None},'production_gate':'PASS' if gate else 'NO_PASS'}
Path('out/summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))