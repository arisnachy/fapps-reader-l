from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import sync_playwright

import gate0a_wnba_full_probe as base

OUT = Path('rules_artifacts')
RULE_RE = re.compile(r'(reglas?|rules?|house rules|términos|terminos|sports rules)', re.I)
BASKETBALL_RE = re.compile(r'(baloncesto|basketball|wnba|nba)', re.I)
SETTLEMENT_RE = re.compile(r'(overtime|tiempo extra|team total|total (?:de |del )?equipo|total puntos|incluye|including)', re.I)


def clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def safe_url(url: str) -> str:
    return base.redact_url(url)


def candidate_links(page):
    rows = page.locator('a[href],button,[onclick]').evaluate_all(
        """
        els => els.map((e,i)=>({
          index:i,
          tag:(e.tagName||'').toLowerCase(),
          text:(e.innerText||e.textContent||'').replace(/\s+/g,' ').trim(),
          href:e.getAttribute('href')||'',
          onclick:e.getAttribute('onclick')||'',
          id:e.id||'',
          class_name:typeof e.className==='string'?e.className:'',
          title:e.getAttribute('title')||''
        }))
        """
    )
    out=[]
    for row in rows:
        hay=' '.join(clean(row.get(k)) for k in ('text','href','onclick','id','class_name','title'))
        if RULE_RE.search(hay):
            row=dict(row)
            row['href']=safe_url(urljoin(page.url, clean(row.get('href')))) if clean(row.get('href')) else ''
            row['onclick']=base.redact_text(clean(row.get('onclick')))
            out.append(row)
    return out


def extract_relevant_text(text: str):
    lines=[clean(x) for x in str(text or '').splitlines() if clean(x)]
    hits=[]
    for i,line in enumerate(lines):
        if BASKETBALL_RE.search(line) or SETTLEMENT_RE.search(line):
            lo=max(0,i-2); hi=min(len(lines),i+3)
            block=' | '.join(lines[lo:hi])
            if block not in hits: hits.append(block)
    return hits[:200]


def navigate_with_retries(page, url: str, attempts: int = 3):
    errors=[]
    for attempt in range(1, attempts+1):
        try:
            resp=page.goto(url,wait_until='domcontentloaded',timeout=120000)
            page.wait_for_timeout(5000)
            return {'ok':True,'attempt':attempt,'status':resp.status if resp else None,'url':safe_url(page.url),'errors':errors}
        except Exception as exc:
            errors.append(f'{type(exc).__name__}: {exc}')
            page.wait_for_timeout(3000)
    return {'ok':False,'attempt':attempts,'url':safe_url(page.url),'errors':errors}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={
      'captured_at_utc':base.now_utc(),
      'mode':'ANONYMOUS_READ_ONLY_SETTLEMENT_RULES_DISCOVERY',
      'guards':['No credentials/account state.','No wager controls are clicked.','Only rule/terms links are followed.','Absence of a public rule page does not imply a settlement rule.'],
      'pages':[]
    }
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(locale='es-DO',timezone_id='America/Santo_Domingo',viewport={'width':1440,'height':1600})
        page=context.new_page()
        nav=navigate_with_retries(page,base.START_URL)
        result['start_navigation']=nav
        if nav['ok']:
            try: body=page.locator('body').inner_text(timeout=5000)
            except Exception: body=''
            links=candidate_links(page)
            result['pages'].append({'url':safe_url(page.url),'title':page.title(),'rule_links':links,'relevant_text':extract_relevant_text(body)})
            destinations=[]
            for row in links:
                href=clean(row.get('href'))
                if not href or href in destinations: continue
                try:
                    host=urlsplit(href).hostname or ''
                except Exception: host=''
                if not host.endswith('juancitosport.com.do'): continue
                if not RULE_RE.search(href+' '+clean(row.get('text'))+' '+clean(row.get('title'))): continue
                destinations.append(href)
            for href in destinations[:12]:
                tab=context.new_page()
                nav2=navigate_with_retries(tab,href,attempts=2)
                rec={'navigation':nav2}
                if nav2['ok']:
                    try: text=tab.locator('body').inner_text(timeout=8000)
                    except Exception: text=''
                    rec.update({'url':safe_url(tab.url),'title':tab.title(),'relevant_text':extract_relevant_text(text),'body_preview':clean(text)[:12000]})
                result['pages'].append(rec)
                tab.close()
        result['captured_at_utc_end']=base.now_utc()
        browser.close()
    hits=[]
    for pg in result['pages']:
        hits.extend(pg.get('relevant_text') or [])
    summary={
      'captured_at_utc':result['captured_at_utc'],
      'captured_at_utc_end':result.get('captured_at_utc_end'),
      'start_navigation':result.get('start_navigation'),
      'rule_page_candidates':sum(len(pg.get('rule_links') or []) for pg in result['pages']),
      'settlement_text_hits':hits[:100],
      'decision':'VERIFIED_PUBLIC_RULE_TEXT_FOUND' if hits else 'RULE_EQUIVALENCE_PENDING'
    }
    (OUT/'JUANCITO_PUBLIC_RULES_RAW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'JUANCITO_PUBLIC_RULES_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
    return 0 if result.get('start_navigation',{}).get('ok') else 2

if __name__=='__main__':
    raise SystemExit(main())
