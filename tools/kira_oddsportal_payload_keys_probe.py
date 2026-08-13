import requests,re,json
from bs4 import BeautifulSoup
url='https://www.oddsportal.com/football/2026-08-10/'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36','Accept-Language':'en-US,en;q=0.9'},timeout=30)
soup=BeautifulSoup(r.text,'html.parser')
for i,sc in enumerate(soup.find_all('script')):
    txt=sc.string or sc.get_text() or ''
    if 'initialRows' not in txt: continue
    print('SCRIPT_INDEX',i,'LEN',len(txt))
    m=re.search(r'self\.__next_f\.push\((\[1,.*\])\)\s*$',txt,re.S)
    if not m:
        print('NO_OUTER_MATCH');continue
    outer=json.loads(m.group(1));payload=outer[1]
    print('PAYLOAD_PREFIX',payload[:80])
    colon=payload.find(':');data=json.loads(payload[colon+1:])
    props=data[3]
    print('PROP_KEYS',list(props.keys()))
    for k,v in props.items():
        if 'odd' in k.lower() or 'row' in k.lower() or 'event' in k.lower():
            print('KEY',k,'TYPE',type(v).__name__,'LEN',len(v) if hasattr(v,'__len__') else None,'SAMPLE',str(v)[:2000])
    # recursively collect key names containing odd and sample paths
    hits=[]
    def walk(x,path='root'):
        if len(hits)>100:return
        if isinstance(x,dict):
            for k,v in x.items():
                if 'odd' in str(k).lower():hits.append((path+'.'+str(k),str(v)[:500]))
                walk(v,path+'.'+str(k))
        elif isinstance(x,list):
            for j,v in enumerate(x[:100]):walk(v,path+f'[{j}]')
    walk(props)
    print('ODD_KEY_HITS',json.dumps(hits[:100],ensure_ascii=False,indent=2))
