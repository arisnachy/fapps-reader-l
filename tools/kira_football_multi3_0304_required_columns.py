from __future__ import annotations

import csv, hashlib, io, json, math
from collections import Counter
from datetime import datetime
from pathlib import Path
import requests

OUT=Path('artifacts/kira_football_multi3_0304')
SEASON='0304'; LEAGUES=['E0','SP1','D1','I1','F1','N1','P1','SC0','B1']
REQ=['Date','HomeTeam','AwayTeam','B365H','B365D','B365A','FTHG','FTAG']
MIN_SOURCE_LEAGUES=5; MIN_N=35; MIN_LCB=.90

def wilson(w,n,z=1.959963984540054):
    if n<=0:return 0.,1.
    p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;m=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
    return max(0,c-m),min(1,c+m)
def pdate(x):
    for f in ('%d/%m/%y','%d/%m/%Y'):
        try:return datetime.strptime(str(x).strip(),f).date().isoformat()
        except ValueError:pass
    return ''
def write(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
def decode(raw):
    for enc in ('utf-8-sig','latin-1'):
        try:return raw.decode(enc),enc
        except UnicodeDecodeError:pass
    raise UnicodeDecodeError('unknown',b'',0,1,'decode failed')
def required_rows(raw):
    text,enc=decode(raw); rr=list(csv.reader(io.StringIO(text)))
    while rr and not any(str(x).strip() for x in rr[0]):rr.pop(0)
    if not rr:return None,{'reason':'EMPTY'}
    header=[str(x).strip() for x in rr[0]]
    missing=[c for c in REQ if c not in header]
    if missing:return None,{'reason':'MISSING_COLUMNS','missing':missing,'header_columns':len(header),'encoding':enc}
    idx={c:header.index(c) for c in REQ}; mx=max(idx.values()); rows=[]; extra=0; short=0; blank=0
    for rawrow in rr[1:]:
        if not any(str(x).strip() for x in rawrow):blank+=1;continue
        if len(rawrow)<=mx:short+=1;continue
        if len(rawrow)>len(header):extra+=1
        rows.append({c:rawrow[i] for c,i in idx.items()})
    # Required-column integrity: nonblank rows too short for required indexes poison whole file.
    if short:return None,{'reason':'ROW_SHORTER_THAN_REQUIRED_INDEX','short_rows':short,'extra_trailing_field_rows':extra,'header_columns':len(header),'encoding':enc}
    return rows,{'reason':'PASS','extra_trailing_field_rows':extra,'blank_rows':blank,'header_columns':len(header),'encoding':enc,'required_indices':idx}
def main():
    OUT.mkdir(parents=True,exist_ok=True);s=requests.Session();s.headers['User-Agent']='KIRA-MULTI3-required-columns/1.0'
    source=[];preg=[];outcomes={};seen=set();dup=0
    for lg in LEAGUES:
        url=f'https://www.football-data.co.uk/mmz4281/{SEASON}/{lg}.csv'
        try:r=s.get(url,timeout=30)
        except Exception as e:source.append({'league':lg,'url':url,'status':'SOURCE_UNUSABLE','reason':type(e).__name__});continue
        if r.status_code!=200:source.append({'league':lg,'url':url,'http':r.status_code,'status':'SOURCE_UNUSABLE','reason':'HTTP'});continue
        raw=r.content;sha=hashlib.sha256(raw).hexdigest()
        try,meta=required_rows(raw)
        if False: pass
        # syntax helper replaced below
