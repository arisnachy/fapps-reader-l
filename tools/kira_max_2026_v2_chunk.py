import asyncio, os
from datetime import date
from pathlib import Path
import kira_max_2026_v2_universal as m

m.START = date.fromisoformat(os.environ['MAX_START'])
m.END = date.fromisoformat(os.environ['MAX_END'])
m.OUT = Path(os.environ['MAX_OUT'])
m.OUT.mkdir(parents=True, exist_ok=True)
m.CONCURRENCY = 4

async def bounded_wait(page):
    await page.wait_for_function("""
      () => Array.from(document.querySelectorAll('div.border-black-borders'))
        .some(e => /^(Finished|After ET|After Pen\.)\s/.test((e.innerText || '').trim()))
    """, timeout=6000)

m.wait_for_historical_rows = bounded_wait
asyncio.run(m.main())
