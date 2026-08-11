from __future__ import annotations
import csv, io, json, urllib.request
from pathlib import Path

BLOCK='0405'
LEAGUES=['E0','SP1','D1','I1','F1','N1','P1','SC0','B1']
OUT=Path('front1_0405_total_schema_probe'); OUT.mkdir(exist_ok=True)
result={}
for lg in LEAGUES:
    url=f'https://www.football-data.co.uk/mmz4281/{BLOCK}/{lg}.csv'
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'KIRA-SchemaProbe/1.0'})
        with urllib.request.urlopen(req,timeout=30) as r: data=r.read()
        text=data.decode('utf-8-sig',errors='replace')
        if '\ufffd' in text: text=data.decode('latin-1')
        reader=csv.DictReader(io.StringIO(text)); fields=reader.fieldnames or []
        result[lg]={
            'url':url,'http_ok':True,'fields':fields,
            'has_B365_over_2_5':'B365>2.5' in fields,
            'has_B365_under_2_5':'B365<2.5' in fields,
            'has_BbAv_over_2_5':'BbAv>2.5' in fields,
            'has_BbAv_under_2_5':'BbAv<2.5' in fields,
            'has_Avg_over_2_5':'Avg>2.5' in fields,
            'has_Avg_under_2_5':'Avg<2.5' in fields,
        }
    except Exception as exc:
        result[lg]={'url':url,'http_ok':False,'error':f'{type(exc).__name__}: {exc}'}
summary={
    'block':BLOCK,'inspection':'SCHEMA_ONLY_NO_RESULT_SCORING',
    'leagues':result,
    'all_have_b365_ou25':all(x.get('has_B365_over_2_5') and x.get('has_B365_under_2_5') for x in result.values()),
    'all_have_any_average_ou25':all((x.get('has_BbAv_over_2_5') and x.get('has_BbAv_under_2_5')) or (x.get('has_Avg_over_2_5') and x.get('has_Avg_under_2_5')) for x in result.values()),
    'guard':'Only CSV headers were inspected. No event rows, scores, total outcomes, candidate list or performance were emitted.'
}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,indent=2,ensure_ascii=False))
