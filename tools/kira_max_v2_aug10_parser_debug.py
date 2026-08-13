import asyncio,json
from datetime import date
from playwright.async_api import async_playwright
from kira_max_2026_v2_universal import expand_show_more,parse_texts

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(headless=True)
        page=await b.new_page(viewport={'width':1600,'height':1200},locale='en-US',timezone_id='UTC')
        await page.goto('https://www.oddsportal.com/matches/football/20260810/',wait_until='domcontentloaded',timeout=60000)
        await page.wait_for_timeout(1500)
        clicks=await expand_show_more(page)
        texts=await page.locator('div.border-black-borders').evaluate_all('(els)=>els.map(e=>e.innerText.trim()).filter(Boolean)')
        pre,outcomes,meta=parse_texts(date(2026,8,10),texts)
        print('CLICKS',clicks,'TEXTS',len(texts),'META',meta,'PRE',len(pre),'OUTCOMES',len(outcomes))
        print('PRE_SAMPLE',json.dumps(pre[:15],ensure_ascii=False,indent=2))
        # Print sequence around first recognizable match-like nodes.
        for i,t in enumerate(texts[:300]):
            x=' '.join(t.split())
            if x.startswith('Football / ') or x.startswith('10 Aug 2026') or x.startswith('Finished') or x.startswith('After '):
                print('NODE',i,repr(x[:500]))
        await b.close()

asyncio.run(main())
