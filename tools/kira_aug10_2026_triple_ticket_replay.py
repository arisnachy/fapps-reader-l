from __future__ import annotations

import csv, hashlib, io, json, math
from datetime import datetime
from pathlib import Path
import requests

OUT = Path('artifacts/kira_aug10_2026_triple_ticket_replay')
OUT.mkdir(parents=True, exist_ok=True)
CODES = ['ARG','AUT','BRA','CHN','DNK','FIN','IRL','JPN','MEX','NOR','POL','ROU','RUS','SWE','SWZ','USA']
REQ = ['Date','Home','Away','League','AvgCH','AvgCD','AvgCA','HG','AG']
TARGET = '2026-08-10'
TH = 0.60
MAX_N = 5


def pdate(s):
    for f in ('%d/%m/%Y','%d/%m/%y'):
        try:
            return datetime.strptime(str(s).strip(), f).date()
        except Exception:
            pass
    return None


def write(path, rows):
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    fields = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def main():
    sess = requests.Session(); sess.headers['User-Agent'] = 'KIRA-AUG10-TRIPLE/1.0'
    audit=[]; pre=[]; outcomes={}; seen=set(); dups=0
    for code in CODES:
        url=f'https://www.football-data.co.uk/new/{code}.csv'
        try:
            r=sess.get(url,timeout=60); r.raise_for_status()
        except Exception as exc:
            audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':type(exc).__name__}); continue
        raw=r.content
        rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))))
        if not rows:
            audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':'EMPTY'}); continue
        h=[x.strip() for x in rows[0]]; miss=[c for c in REQ if c not in h]
        if miss:
            audit.append({'source':code,'status':'SOURCE_UNUSABLE','reason':'MISSING_COLUMNS','missing':miss}); continue
        idx={c:h.index(c) for c in REQ}; mx=max(idx.values()); target_rows=0; eligible=0
        for row in rows[1:]:
            if len(row)<=mx: continue
            d=pdate(row[idx['Date']])
            if d is None or d.isoformat()!=TARGET: continue
            target_rows += 1
            home=row[idx['Home']].strip(); away=row[idx['Away']].strip(); league=row[idx['League']].strip()
            try:
                h1=float(row[idx['AvgCH']]); dr=float(row[idx['AvgCD']]); a1=float(row[idx['AvgCA']])
                hg=int(float(row[idx['HG']])); ag=int(float(row[idx['AG']]))
            except Exception:
                continue
            if not home or not away or not all(math.isfinite(x) and x>1 for x in (h1,dr,a1)): continue
            qh,qd,qa=1/h1,1/dr,1/a1; den=qh+qd+qa; ph,pa=qh/den,qa/den
            if ph==pa: continue
            side='HOME' if ph>pa else 'AWAY'; prob=max(ph,pa)
            if prob<TH: continue
            price=h1 if side=='HOME' else a1; ent=home if side=='HOME' else away
            key=(d.isoformat(),code,league,home,away)
            if key in seen: dups+=1; continue
            seen.add(key); eid='A10-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            pre.append({'date':TARGET,'source':code,'league':league,'Home':home,'Away':away,'selected_side':side,'selected_entity':ent,'selected_price':price,'p_favorite_novig':prob,'event_id':eid})
            outcomes[eid]={'HG':hg,'AG':ag}; eligible += 1
        audit.append({'source':code,'status':'PASS','file_sha256':hashlib.sha256(raw).hexdigest(),'target_rows':target_rows,'eligible_pre_cap':eligible})

    if len(audit)!=len(CODES) or any(x.get('status')!='PASS' for x in audit):
        res={'decision':'SOURCE_GATE_FAIL','source_audit':audit}; (OUT/'summary.json').write_text(json.dumps(res,indent=2)); print(json.dumps(res,indent=2)); return
    if dups: raise SystemExit(f'DUPLICATES={dups}')

    ranked=sorted(pre,key=lambda x:(-x['p_favorite_novig'],x['selected_price'],x['source'],x['league'],x['Home'],x['Away'],0 if x['selected_side']=='HOME' else 1))
    frozen=[]
    for rank,x in enumerate(ranked[:MAX_N],1): frozen.append({**x,'date_rank':rank,'eligible_count_on_date':len(ranked)})
    write(OUT/'rank1_5_pre_settlement.csv',frozen)
    ledger_sha=hashlib.sha256((OUT/'rank1_5_pre_settlement.csv').read_bytes()).hexdigest()

    settled=[]
    for x in frozen:
        o=outcomes[x['event_id']]
        gd=(o['HG']-o['AG']) if x['selected_side']=='HOME' else (o['AG']-o['HG'])
        settled.append({**x,**o,'selected_goal_diff':gd,'hit':gd+1.5>0})
    write(OUT/'rank1_5_settled.csv',settled)

    tickets={}
    for n in (3,4,5):
        if len(settled)<n:
            tickets[str(n)]={'N':n,'status':'NOT_ENOUGH_ELIGIBLE','eligible_count':len(settled)}; continue
        rr=settled[:n]; survived=all(bool(x['hit']) for x in rr)
        tickets[str(n)]={'N':n,'status':'SETTLED','survived':survived,'wins':sum(bool(x['hit']) for x in rr),'losses':sum(not bool(x['hit']) for x in rr),'entities':[x['selected_entity'] for x in rr],'event_ids':[x['event_id'] for x in rr]}

    res={'hypothesis_id':'AUG10_2026_TRIPLE_TICKET_REPLAY','status':'RETROSPECTIVE_REPLAY_ONLY','target_date':TARGET,'threshold':TH,'candidate_generation_used_outcomes':False,'duplicate_event_keys':dups,'eligible_count':len(ranked),'pre_settlement_ledger_sha256':ledger_sha,'frozen_ranked_candidates':[{k:x[k] for k in ('date_rank','source','league','Home','Away','selected_entity','selected_side','selected_price','p_favorite_novig','event_id')} for x in frozen],'tickets':tickets,'source_audit':audit}
    (OUT/'summary.json').write_text(json.dumps(res,indent=2),encoding='utf-8'); print(json.dumps(res,indent=2))

if __name__=='__main__': main()
