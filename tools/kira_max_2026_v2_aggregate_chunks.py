from __future__ import annotations
import csv,glob,hashlib,json,math
from collections import defaultdict
from pathlib import Path

ROOT=Path('chunk_artifacts');OUT=Path('artifacts/kira_max_2026_v2_chunked');OUT.mkdir(parents=True,exist_ok=True)
EXPECTED_DAYS=224;NS=(3,4,5);MIN_DATES=35;OBS_FLOOR=.90;WILSON_FLOOR=.90

def wilson(w,n,z=1.959963984540054):
    if n<=0:return 0.0,1.0
    p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
    return max(0,c-m),min(1,c+m)
def read_csv(p):
    with open(p,newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def write_csv(p,rows):
    if not rows:p.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    summaries=[];calendar=[];settled=[];pre=[]
    for p in sorted(ROOT.glob('**/summary.json')):summaries.append(json.loads(p.read_text(encoding='utf-8')))
    for p in sorted(ROOT.glob('**/calendar.csv')):calendar.extend(read_csv(p))
    for p in sorted(ROOT.glob('**/rank1_5_settled.csv')):settled.extend(read_csv(p))
    for p in sorted(ROOT.glob('**/rank1_5_pre_settlement.csv')):pre.extend(read_csv(p))
    if len(summaries)!=8:raise SystemExit(f'EXPECTED_8_SUMMARIES_GOT_{len(summaries)}')
    bydate={}
    for r in calendar:
        d=r['date']
        if d in bydate:raise SystemExit(f'DUPLICATE_CALENDAR_DATE {d}')
        bydate[d]=r
    if len(bydate)!=EXPECTED_DAYS:raise SystemExit(f'EXPECTED_{EXPECTED_DAYS}_DAYS_GOT_{len(bydate)}')
    pre=sorted(pre,key=lambda r:(r['date'],int(r['date_rank'])))
    write_csv(OUT/'rank1_5_pre_settlement_combined.csv',pre)
    ledger_sha=hashlib.sha256((OUT/'rank1_5_pre_settlement_combined.csv').read_bytes()).hexdigest()
    sd=defaultdict(list)
    for r in settled:sd[r['date']].append(r)
    for d in sd:sd[d]=sorted(sd[d],key=lambda r:int(r['date_rank']))
    per_n={};failures=[]
    for n in NS:
        tickets=[]
        for d in sorted(bydate):
            eligible=int(bydate[d]['eligible_count'])
            if eligible<n:continue
            rr=sd[d][:n]
            if len(rr)!=n:raise SystemExit(f'PREFIX_MISMATCH {d} N{n}')
            vals=[]
            for x in rr:
                h=str(x.get('hit','')).strip().lower()
                vals.append(None if h in ('','none') else h=='true')
            unr=any(v is None for v in vals);surv=None if unr else all(vals)
            t={'date':d,'N':n,'status':'UNRESOLVED' if unr else ('WIN' if surv else 'LOSS'),'survived':surv,
               'entities':'|'.join(x['selected_entity'] for x in rr),'competitions':'|'.join(x['competition'] for x in rr)}
            tickets.append(t)
            if surv is False:failures.append(t)
        ev=[t for t in tickets if t['survived'] is not None];wins=sum(t['survived'] is True for t in ev);total=len(ev);l,u=wilson(wins,total);rate=wins/total if total else 0
        per_n[str(n)]={'N':n,'available_dates':len(tickets),'evaluable_dates':total,'unresolved_dates':len(tickets)-total,
                       'ticket_wins':wins,'ticket_losses':total-wins,'ticket_survival':rate,'ticket_wilson95_lcb':l,'ticket_wilson95_ucb':u,
                       'certainty_pass':total>=MIN_DATES and rate>OBS_FLOOR and l>=WILSON_FLOOR}
        write_csv(OUT/f'tickets_T{n}.csv',tickets)
    core3=sum(int(r['eligible_count'])>=3 for r in bydate.values());full5=sum(int(r['eligible_count'])>=5 for r in bydate.values())
    availability={'calendar_days':EXPECTED_DAYS,'core3_days':core3,'core3_rate':core3/EXPECTED_DAYS,'full_stack_days':full5,'full_stack_rate':full5/EXPECTED_DAYS,'daily_availability_pass':full5==EXPECTED_DAYS}
    failed_dates=[];conflicts=0;unresolved=0
    for s in summaries:
        failed_dates.extend(s.get('failed_dates',[]));conflicts+=int(s.get('conflicting_duplicate_events',0));unresolved+=int(s.get('unresolved_ranked_legs',0))
    evidence_complete=(not failed_dates and conflicts==0 and unresolved==0)
    certainty_all=all(per_n[str(n)]['certainty_pass'] for n in NS)
    decision='PIN_MAX_2026_V2_PASS' if evidence_complete and availability['daily_availability_pass'] and certainty_all else ('EVIDENCE_INCOMPLETE_DO_NOT_PIN' if not evidence_complete else 'NO_PASS_DO_NOT_PIN')
    res={'hypothesis_id':'MAX_2026_V2_UNIVERSAL_CHUNKED_REPLICATION','decision':decision,'preregistration':'MAX_2026_V2_PREREGISTRATION.md',
         'candidate_generation_used_outcomes':False,'chunks':8,'calendar_start':'2026-01-01','calendar_end':'2026-08-12','calendar_days':EXPECTED_DAYS,
         'pre_settlement_ledger_sha256':ledger_sha,'failed_dates':sorted(set(failed_dates)),'conflicting_duplicate_events':conflicts,'unresolved_ranked_legs':unresolved,
         'evidence_complete':evidence_complete,'availability':availability,'per_n':per_n}
    write_csv(OUT/'calendar_combined.csv',[bydate[d] for d in sorted(bydate)]);write_csv(OUT/'failed_tickets.csv',failures)
    (OUT/'summary.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print('FINAL_CHUNKED_SUMMARY');print(json.dumps(res,indent=2))
if __name__=='__main__':main()
