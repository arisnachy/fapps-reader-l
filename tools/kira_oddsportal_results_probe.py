from playwright.sync_api import sync_playwright
import json
URL='https://www.oddsportal.com/football/europe/champions-league/results/'
selectors=['div.eventRow','div[class*="eventRow"]','div.border-black-borders','a[href*="/football/europe/champions-league/"]']
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    page=b.new_page(viewport={'width':1600,'height':1200},locale='en-US',timezone_id='UTC')
    page.goto(URL,wait_until='domcontentloaded',timeout=60000)
    page.wait_for_timeout(4000)
    print('TITLE',page.title())
    print('URL',page.url)
    out={}
    for sel in selectors:
        try:
            els=page.locator(sel); n=els.count(); vals=[]
            for i in range(min(n,25)):
                txt=' '.join(els.nth(i).inner_text(timeout=3000).split())
                href=None
                try:href=els.nth(i).get_attribute('href')
                except:pass
                vals.append({'text':txt[:500],'href':href})
            out[sel]={'count':n,'rows':vals}
        except Exception as e:out[sel]={'error':repr(e)}
    print(json.dumps(out,ensure_ascii=False,indent=2))
    print('BODY_SAMPLE',' '.join(page.locator('body').inner_text().split())[:5000])
    b.close()
