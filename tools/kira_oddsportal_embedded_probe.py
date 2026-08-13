import requests,re,json
from bs4 import BeautifulSoup
url='https://www.oddsportal.com/football/2026-08-10/'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36','Accept-Language':'en-US,en;q=0.9'},timeout=30)
s=r.text
needle='\\"home-name\\":\\"Santa Clara\\"'
pos=s.find(needle)
print('LEN',len(s),'POS',pos)
print('AROUND',s[max(0,pos-2500):pos+8000])
keys=['odds','home-name','away-name','event-stage-name','moneyline','1x2','bookmaker','home-odds','away-odds','draw-odds']
for k in keys: print('COUNT',k,s.lower().count(k.lower()))
# print script tag types/ids and sizes so we can identify the Next payload
soup=BeautifulSoup(s,'html.parser')
for i,sc in enumerate(soup.find_all('script')):
    txt=sc.string or sc.get_text() or ''
    if 'Santa Clara' in txt or 'odds' in txt.lower():
        print('SCRIPT',i,'id=',sc.get('id'),'type=',sc.get('type'),'len=',len(txt),'sample=',txt[:1000])
