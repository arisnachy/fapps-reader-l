import asyncio
import kira_max_2026_v2_universal as m

m.CONCURRENCY = 4

async def fast_wait(page):
    await page.wait_for_function("""
      () => Array.from(document.querySelectorAll('div.border-black-borders'))
        .some(e => /^(Finished|After ET|After Pen\.)\s/.test((e.innerText || '').trim()))
    """, timeout=6000)

m.wait_for_historical_rows = fast_wait
asyncio.run(m.main())
