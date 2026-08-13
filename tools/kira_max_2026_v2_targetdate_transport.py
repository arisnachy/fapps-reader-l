from __future__ import annotations
import asyncio, os, random
from datetime import date
from pathlib import Path
import kira_max_2026_v2_universal as m

if os.environ.get('MAX_START'):
    m.START=date.fromisoformat(os.environ['MAX_START'])
if os.environ.get('MAX_END'):
    m.END=date.fromisoformat(os.environ['MAX_END'])
if os.environ.get('MAX_OUT'):
    m.OUT=Path(os.environ['MAX_OUT']);m.OUT.mkdir(parents=True,exist_ok=True)
m.CONCURRENCY=int(os.environ.get('MAX_CONCURRENCY','4'))

async def robust_fetch_one(browser,target,sem):
    url=f'https://www.oddsportal.com/matches/football/{target.strftime("%Y%m%d")}/'
    target_label=target.strftime('%d %b %Y')
    async with sem:
        last=None
        for attempt in range(1,4):
            page=await browser.new_page(viewport={'width':1600,'height':1200},locale='en-US',timezone_id='UTC')
            try:
                await page.goto(url,wait_until='domcontentloaded',timeout=45000)
                await page.wait_for_function("""
                  (label) => Array.from(document.querySelectorAll('div.border-black-borders'))
                    .some(e => ((e.innerText || '').trim()).startsWith(label))
                """, arg=target_label, timeout=10000)
                await page.wait_for_function("""
                  () => Array.from(document.querySelectorAll('div.border-black-borders'))
                    .some(e => /^(Finished|After ET|After Pen\.)\s/.test((e.innerText || '').trim()))
                """, timeout=10000)
                await page.wait_for_timeout(500)
                clicks=await m.expand_show_more(page)
                texts=await page.locator('div.border-black-borders').evaluate_all('(els)=>els.map(e=>e.innerText.trim()).filter(Boolean)')
                body=await page.locator('body').inner_text(timeout=5000)
                resolved=page.url
                if 'Next Football Matches' not in body or len(body)<200:raise RuntimeError('DATE_PAGE_NOT_LOADED')
                pre,outcomes,meta=m.parse_texts(target,texts)
                if meta['parsed_result_rows']<=0:raise RuntimeError('NO_PARSED_RESULT_ROWS')
                if meta['numeric_target_rows']<=0:raise RuntimeError('NO_NUMERIC_TARGET_ROWS')
                await page.close()
                return {'date':target.isoformat(),'status':'PASS','requested_url':url,'resolved_url':resolved,'show_more_clicks':clicks,
                        'candidate_rows':pre,'outcomes':outcomes,**meta}
            except Exception as exc:
                last=f'{type(exc).__name__}:{exc}'
                try:await page.close()
                except:pass
                if attempt<3:await asyncio.sleep(.8*attempt+random.random()*.4)
        return {'date':target.isoformat(),'status':'FAIL','requested_url':url,'reason':last,'candidate_rows':[],'outcomes':{},
                'show_more_clicks':0,'parsed_result_rows':0,'numeric_target_rows':0}

m.fetch_one=robust_fetch_one
asyncio.run(m.main())
