from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

URL = 'https://lineas.juancitosport.com.do/ubet_revolution/lineas_tvOnline/juancitosport/mlb.php'
OUT = Path('artifacts/kira_juancito_srl_period_settlement_v27')
TZ = ZoneInfo('America/Santo_Domingo')


def clean(v):
    return re.sub(r'\s+', ' ', str(v or '')).strip()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    evidence = {
        'captured_at_local': datetime.now(TZ).isoformat(),
        'source_url': URL,
        'read_only': True,
        'navigation_attempts': [],
    }
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(locale='es-DO', timezone_id='America/Santo_Domingo')
        page = ctx.new_page()
        loaded = False
        for attempt in range(1, 6):
            try:
                response = page.goto(URL, wait_until='commit', timeout=45000)
                page.wait_for_timeout(5000)
                text = clean(page.locator('body').inner_text(timeout=5000))
                evidence['navigation_attempts'].append({'attempt':attempt,'status':response.status if response else None,'body_chars':len(text)})
                if text:
                    loaded = True
                    break
            except Exception as exc:
                evidence['navigation_attempts'].append({'attempt':attempt,'error':f'{type(exc).__name__}: {exc}'})
        if not loaded:
            evidence.update({'status':'INFRA_TRANSIENT','period_decision':'MARKET_DATA_PENDING','settlement_decision':'MARKET_DATA_PENDING'})
            (OUT/'result.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(evidence,ensure_ascii=False,indent=2)); browser.close(); raise SystemExit(3)

        body = clean(page.locator('body').inner_text())
        evidence['body_excerpt'] = body[:20000]
        try:
            rows = page.locator('tr').evaluate_all("""els=>els.map((tr,i)=>({index:i,text:(tr.innerText||tr.textContent||'').replace(/\s+/g,' ').trim(),cells:Array.from(tr.querySelectorAll('th,td')).map(x=>(x.innerText||x.textContent||'').replace(/\s+/g,' ').trim())})).filter(x=>x.text)""")
        except Exception:
            rows = []
        evidence['table_rows'] = rows[:500]

        full_game_rows = [r for r in rows if re.search(r'JUEGO\s+COMPLETO', r.get('text',''), re.I)]
        srl_rows = [r for r in rows if re.search(r'\bSRL\b|SUPER\s+RUN\s+LINE', r.get('text',''), re.I)]
        # Strong structural pass requires an actual table row/header structure containing
        # the full-game section and SRL in the same header band or adjacent header rows.
        structural_pairs = []
        for a in full_game_rows:
            for b in srl_rows:
                if abs(int(a.get('index',0))-int(b.get('index',0))) <= 2:
                    structural_pairs.append({'full_game_row':a,'srl_row':b})
        body_pattern = bool(re.search(r'JUEGO\s+COMPLETO.{0,500}\bSRL\b', body, re.I))
        period_pass = bool(structural_pairs or body_pattern)

        settlement_needles = re.compile(r'(?i)(super\s*run\s*line.{0,600}(?:empate|push|reembolso|refund|void|anulad|extra\s+inning|entrada)|(?:empate|push|reembolso|refund|void|anulad|extra\s+inning|entrada).{0,600}super\s*run\s*line)')
        settlement_hits = []
        for match in settlement_needles.finditer(body):
            settlement_hits.append(body[max(0,match.start()-500):match.end()+1000])
        evidence['settlement_hits'] = settlement_hits[:50]

        # Also inspect same-origin links/scripts for explicit SRL settlement language.
        fetched_hits = []
        try:
            urls = page.evaluate("Array.from(new Set([...Array.from(document.scripts).map(s=>s.src),...Array.from(document.querySelectorAll('a[href]')).map(a=>a.href)].filter(Boolean)))")
        except Exception:
            urls = []
        for url in urls[:200]:
            if 'juancitosport.com.do' not in str(url).lower():
                continue
            try:
                rec = page.evaluate("""async u=>{try{const r=await fetch(u,{credentials:'same-origin'});const t=await r.text();return {status:r.status,url:r.url,text:t.slice(0,1000000)}}catch(e){return {url:u,error:String(e)}}}""", url)
            except Exception:
                continue
            text = rec.get('text','')
            if re.search(r'(?i)super\s*run\s*line|\bSRL\b', text) and re.search(r'(?i)push|tie|refund|void|empate|reembolso|anulad|extra\s+inning|entrada', text):
                snippets=[]
                for m in re.finditer(r'(?i)super\s*run\s*line|\bSRL\b', text):
                    snippets.append(clean(text[max(0,m.start()-1200):m.start()+3000]))
                    if len(snippets)>=20: break
                fetched_hits.append({'url':rec.get('url'),'status':rec.get('status'),'snippets':snippets})
        evidence['linked_settlement_hits'] = fetched_hits
        settlement_pass = bool(settlement_hits or fetched_hits)
        evidence['status'] = 'SRL_PERIOD_PASS_SETTLEMENT_PASS' if period_pass and settlement_pass else ('SRL_PERIOD_PASS_SETTLEMENT_PENDING' if period_pass else 'SRL_PERIOD_PENDING')
        evidence['period_decision'] = 'FULL_GAME_OPERATOR_EXACT_PASS' if period_pass else 'MARKET_DATA_PENDING'
        evidence['settlement_decision'] = 'OPERATOR_EXACT_SETTLEMENT_TEXT_CAPTURED' if settlement_pass else 'RULE_EQUIVALENCE_PENDING'
        evidence['period_evidence_pairs'] = structural_pairs[:20]
        evidence['body_pattern_pass'] = body_pattern
        browser.close()

    summary = {k:evidence[k] for k in ('captured_at_local','status','period_decision','settlement_decision','body_pattern_pass')}
    summary['period_evidence_pair_count'] = len(evidence.get('period_evidence_pairs') or [])
    summary['settlement_hit_count'] = len(evidence.get('settlement_hits') or []) + len(evidence.get('linked_settlement_hits') or [])
    (OUT/'result.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    raise SystemExit(0 if evidence['period_decision']=='FULL_GAME_OPERATOR_EXACT_PASS' else 3)


if __name__=='__main__':
    main()
