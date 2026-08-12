from __future__ import annotations
import csv,io,json,hashlib
from collections import Counter
from pathlib import Path
import requests

OUT=Path('artifacts/kira_summer_football_bra_usa_schema');OUT.mkdir(parents=True,exist_ok=True)
SOURCES={'BRA':'https://www.football-data.co.uk/new/BRA.csv','USA':'https://www.football-data.co.uk/new/USA.csv'}

def main():
    out={}
    for code,url in SOURCES.items():
        r=requests.get(url,headers={'User-Agent':'KIRA-SUMMER-schema/1.0'},timeout=60);r.raise_for_status();raw=r.content
        text=raw.decode('utf-8-sig',errors='replace');rows=list(csv.reader(io.StringIO(text)))
        header=[x.strip() for x in rows[0]] if rows else []
        # Audit only dates and prematch price columns. Never read score/result fields here.
        date_i=header.index('Date') if 'Date' in header else None
        years=Counter();samples=[]
        if date_i is not None:
            for row in rows[1:]:
                if len(row)<=date_i:continue
                s=row[date_i].strip()
                if not s:continue
                y=None
                for part in reversed(s.replace('-','/').split('/')):
                    if part.isdigit() and len(part)==4:y=int(part);break
                if y is None and len(s)>=2:
                    try:
                        yy=int(s[-2:]);y=2000+yy if yy<80 else 1900+yy
                    except:pass
                if y:years[y]+=1
                if len(samples)<5:samples.append(s)
        price_cols=[c for c in header if c.upper() in {'B365H','B365D','B365A','PSH','PSD','PSA','PH','PD','PA','MAXH','MAXD','MAXA','AVGH','AVGD','AVGA'}]
        out[code]={'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'rows_ex_header':max(0,len(rows)-1),'header':header,'prematch_price_columns':price_cols,'date_samples':samples,'rows_by_year_from_date_only':dict(sorted(years.items()))}
    (OUT/'schema.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
