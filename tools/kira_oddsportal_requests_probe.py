import requests,re
url='https://www.oddsportal.com/football/2026-08-10/'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36','Accept-Language':'en-US,en;q=0.9'},timeout=30)
print('STATUS',r.status_code,'LEN',len(r.text),'URL',r.url)
for needle in ['Santa Clara','Plymouth','Flamengo RJ','1.89','Leagues Cup','Next Football Matches']:
    print(needle,needle in r.text)
for m in re.findall(r'.{0,120}Santa Clara.{0,250}',r.text,re.S)[:3]: print('SAMPLE',m[:500])
