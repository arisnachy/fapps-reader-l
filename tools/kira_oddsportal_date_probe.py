from playwright.sync_api import sync_playwright
import json,re
URL='https://www.oddsportal.com/matches/football/20260810/'
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    page=b.new_page(viewport={'width':1600,'height':1200},locale='en-US',timezone_id='UTC')
    page.goto(URL,wait_until='domcontentloaded',timeout=60000); page.wait_for_timeout(5000)
    print('TITLE',page.title()); print('URL',page.url)
    body=' '.join(page.locator('body').inner_text().split()); print('BODY_SAMPLE',body[:10000])
    sels=['div.border-black-borders','div[class*="eventRow"]','a[href*="/football/"]']
    for sel in sels:
        loc=page.locator(sel); vals=[]
        for i in range(min(loc.count(),2000)):
            try:
                t=' '.join(loc.nth(i).inner_text(timeout=500).split())
                if t: vals.append(t[:700])
            except:pass
        print('SEL',sel,'COUNT',loc.count(),'SAMPLES',json.dumps(vals[:150],ensure_ascii=False,indent=2))
    b.close()
