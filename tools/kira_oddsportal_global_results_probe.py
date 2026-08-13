from playwright.sync_api import sync_playwright
import json,re
BASE='https://www.oddsportal.com/football/results/'
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    page=b.new_page(viewport={'width':1600,'height':1200},locale='en-US',timezone_id='UTC')
    page.goto(BASE,wait_until='domcontentloaded',timeout=60000);page.wait_for_timeout(3500)
    print('TITLE',page.title());print('URL',page.url)
    body=' '.join(page.locator('body').inner_text().split())
    print('BODY_SAMPLE',body[:7000])
    links=[]
    for a in page.locator('a').all():
        try:
            txt=' '.join(a.inner_text(timeout=1000).split());href=a.get_attribute('href')
            if href and ('page' in href.lower() or txt.isdigit()): links.append({'text':txt,'href':href})
        except: pass
    print('PAGINATION',json.dumps(links[-100:],ensure_ascii=False,indent=2))
    nodes=page.locator('div.border-black-borders'); vals=[]
    for i in range(nodes.count()):
        try:
            t=' '.join(nodes.nth(i).inner_text(timeout=800).split())
            if re.match(r'^\d{2} [A-Z][a-z]{2} 20\d{2}',t) or re.match(r'^(Finished|After ET|After Pen\.)',t): vals.append(t[:500])
        except:pass
    print('ROWS',json.dumps(vals[:100],ensure_ascii=False,indent=2))
    b.close()
