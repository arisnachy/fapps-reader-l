from __future__ import annotations
import csv,io,json,math
from collections import Counter
from pathlib import Path
import requests
OUT=Path('artifacts/kira_summer_football_price_availability');OUT.mkdir(parents=True,exist_ok=True)
SOURCES={'BRA':'https://www.football-data.co.uk/new/BRA.csv','USA':'https://www.football-data.co.uk/new/USA.csv'}
YEARS=[2022,2023,2025]
SETS={'B365C':['B365CH','B365CD','B365CA'],'AvgC':['AvgCH','AvgCD','AvgCA'],'PSC':['PSCH','PSCD','PSCA']}
def year(s):
    try:return int(str(s).strip().split('/')[-1])
    except:return None
def main():
    out={}
    for code,url in SOURCES.items():
        raw=requests.get(url,headers={'User-Agent':'KIRA-price-availability/1.0'},timeout=60).content
        rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))));h=[x.strip() for x in rows[0]];idx={c:h.index(c) for cols in SETS.values() for c in cols if c in h};di=h.index('Date')
        info={}
        for y in YEARS:
            yi={}
            rr=[r for r in rows[1:] if len(r)>di and year(r[di])==y]
            for name,cols in SETS.items():
                n=0;fav60=0;fav55=0
                for r in rr:
                    try:a,b,c=(float(r[idx[x]]) for x in cols)
                    except:continue
                    if not all(math.isfinite(x) and x>1 for x in (a,b,c)):continue
                    n+=1;q=[1/a,1/b,1/c];p=max(q[0],q[2])/sum(q);fav60+=p>=.60;fav55+=p>=.55
                yi[name]={'valid_1x2_rows':n,'favorite_p_ge_060_rows':fav60,'favorite_p_ge_055_rows':fav55}
            info[str(y)]={'rows':len(rr),'price_sets':yi}
        out[code]=info
    (OUT/'availability.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
