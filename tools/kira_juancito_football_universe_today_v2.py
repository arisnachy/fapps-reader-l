from __future__ import annotations

import html, json, math, re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

START = 'https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT = Path('artifacts/kira_juancito_football_universe_today_v2')
TZ = ZoneInfo('America/Santo_Domingo')


def clean(v):
    return re.sub(r'\s+', ' ', str(v or '').replace('\xa0', ' ')).strip()


def american_decimal(a):
    a = float(a)
    if a == 0:
        return None
    return 1.0 + (a / 100.0 if a > 0 else 100.0 / abs(a))


def normalize_js(body):
    s = html.unescape(str(body or ''))
    s = s.replace("\\'", "'").replace('\\n', '\n').replace('\\r', '')
    return s


def parse_events(body, source_url):
    s = normalize_js(body)
    out = []
    starts = list(re.finditer(r'newE\s*=\s*new\s+Event\((.*?)\);', s, re.S))
    for i, m in enumerate(starts):
        payload = m.group(1)
        if not re.search(r"['\"]Soccer['\"]", payload, re.I):
            continue
        hm = re.match(
            r"\s*(-?\d+)\s*,\s*(\d+)\s*,\s*'([^']*)'\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)",
            payload,
            re.S,
        )
        if not hm:
            continue
        header_id, event_id = int(hm.group(1)), int(hm.group(2))
        y, mo, d, hh, mm = map(int, hm.groups()[3:8])
        end = starts[i + 1].start() if i + 1 < len(starts) else min(len(s), m.end() + 12000)
        block = s[m.end():end]
        parts = {}
        prx = re.compile(
            r"newP\s*=\s*new\s+Participant\(\s*(\d+)\s*,\s*([123])\s*,\s*'([^']*)'\s*,\s*'[^']*'\s*,\s*'[^']*'\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)",
            re.S,
        )
        for pm in prx.finditer(block):
            if int(pm.group(1)) != event_id:
                continue
            idx = int(pm.group(2))
            parts[idx] = {
                'name': clean(pm.group(3)),
                'moneyline_american': float(pm.group(4)),
                'base_spread': float(pm.group(5)),
                'base_spread_price_american': float(pm.group(6)),
            }
        ev = {
            'header_id': header_id,
            'event_id': event_id,
            'title': clean(hm.group(3)),
            'date_local': f'{y:04d}-{mo:02d}-{d:02d}',
            'time_local': f'{hh:02d}:{mm:02d}',
            'participants': parts,
            'source_url': source_url,
        }
        if all(k in parts and parts[k]['moneyline_american'] != 0 for k in (1, 2, 3)):
            decs = {k: american_decimal(parts[k]['moneyline_american']) for k in (1, 2, 3)}
            inv = {k: 1.0 / decs[k] for k in decs}
            z = sum(inv.values())
            ev['p_home_novig'] = inv[1] / z
            ev['p_away_novig'] = inv[2] / z
            ev['p_draw_novig'] = inv[3] / z
        out.append(ev)
    return out


def related_rows(page, event_id):
    rows = page.locator('[id]').evaluate_all(
        "els=>els.filter(e=>/^(SZ)?PS_\\d+_[123]$/i.test(e.id||'')).map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),row:(e.closest('tr')?(e.closest('tr').innerText||e.closest('tr').textContent):'').replace(/\\s+/g,' ').trim(),cls:typeof e.className==='string'?e.className:''}))"
    )
    hits = []
    for x in rows:
        m = re.match(r'^(?:SZ)?PS_(\d+)_([123])$', x['id'], re.I)
        if not m or int(m.group(1)) != event_id or int(m.group(2)) != 1:
            continue
        txt = clean(x['text'])
        lm = re.search(r'([+-]\d+(?:\.5)?)\s+([+-]\d{3,4})', txt)
        if lm and abs(float(lm.group(1)) - 1.5) < 1e-9:
            hits.append({
                'cell_id': x['id'], 'line': 1.5, 'american_price': int(lm.group(2)),
                'text': txt, 'row': clean(x['row']),
                'actionable': ('tooltip_addBet' in clean(x.get('cls'))) and ('cellCandado' not in clean(x.get('cls'))),
            })
    return hits


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    captured = []
    nav_nodes = []
    result = {
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'captured_at_local': datetime.now(TZ).isoformat(),
        'read_only': True,
        'start_url': START,
        'today_local': str(datetime.now(TZ).date()),
        'selector_gate': 'HOME p_home_novig >= 0.75; distinct events; no market-based candidate creation',
    }
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(locale='es-DO', timezone_id='America/Santo_Domingo', viewport={'width': 1440, 'height': 1400})
        page = ctx.new_page()

        def on_response(resp):
            if 'juancitosport.com.do' not in resp.url:
                return
            if resp.request.resource_type not in {'xhr', 'fetch'}:
                return
            try:
                body = resp.text()
            except Exception:
                return
            if 'new Event(' in body or 'new\\s+Event(' in body or '_method=GetUpcomingEvents' in resp.url or '_method=RefreshSelectedHeader' in resp.url:
                captured.append({'url': resp.url, 'status': resp.status, 'body': body})

        page.on('response', on_response)
        r = page.goto(START, wait_until='domcontentloaded', timeout=120000)
        result['http'] = r.status if r else None
        page.wait_for_timeout(14000)
        result['final_url'] = page.url

        # Read navigation candidates only; never click odds/bet cells here.
        try:
            nav_nodes = page.locator('a,button,[onclick]').evaluate_all(
                "els=>els.map(e=>({tag:e.tagName,id:e.id||'',cls:typeof e.className==='string'?e.className:'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim(),onclick:e.getAttribute('onclick')||'',visible:!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)})).filter(x=>x.visible&&x.text&&x.text.length<=80&&!/^(SZ)?(ML|PS|TT)_/i.test(x.id)&&!/(tooltip_addBet|cellCandado)/i.test(x.cls)).slice(0,2500)"
            )
        except Exception:
            nav_nodes = []

        # Safe sport-level click attempt. It is navigation only, never a wager cell.
        clicked = False
        for label in ('FÚTBOL', 'Fútbol', 'FUTBOL', 'Futbol', 'Soccer'):
            loc = page.get_by_text(label, exact=True)
            for i in range(loc.count()):
                try:
                    n = loc.nth(i)
                    meta = n.evaluate("e=>({id:e.id||'',cls:typeof e.className==='string'?e.className:'',onclick:e.getAttribute('onclick')||''})")
                    if re.match(r'^(?:SZ)?(?:ML|PS|TT)_', meta.get('id',''), re.I) or re.search(r'tooltip_addBet|cellCandado', meta.get('cls',''), re.I):
                        continue
                    if n.is_visible():
                        n.click(force=True, timeout=6000)
                        clicked = True
                        page.wait_for_timeout(5000)
                        break
                except Exception:
                    pass
            if clicked:
                break
        result['soccer_nav_clicked'] = clicked
        page.wait_for_timeout(3000)

        events_by_id = {}
        source_bodies = 0
        for rec in captured:
            evs = parse_events(rec['body'], rec['url'])
            if evs:
                source_bodies += 1
            for ev in evs:
                events_by_id[ev['event_id']] = ev

        today = result['today_local']
        all_soccer = sorted(events_by_id.values(), key=lambda x: (x['date_local'], x['time_local'], x['event_id']))
        today_soccer = [x for x in all_soccer if x['date_local'] == today]
        today_complete = [x for x in today_soccer if 'p_home_novig' in x]
        home_qual = sorted([x for x in today_complete if x['p_home_novig'] >= 0.75], key=lambda x: (-x['p_home_novig'], x['event_id']))

        # Exact +1.5 lookup only for sports-qualified HOME candidates, preserving contract-first integrity.
        details = []
        for ev in home_qual[:12]:
            d = {'event': ev}
            try:
                if not page.evaluate("typeof RelatedEvents === 'function'"):
                    d['state'] = 'RELATED_EVENTS_FUNCTION_MISSING'
                else:
                    page.evaluate("([h,e])=>RelatedEvents(h,e,1,0)", [ev['header_id'], ev['event_id']])
                    page.wait_for_timeout(1800)
                    hits = related_rows(page, ev['event_id'])
                    body = clean(page.locator('body').inner_text(timeout=15000)).lower()
                    d['plus1_5_home_rows'] = hits
                    d['game_section_text_seen'] = ('game lines' in body or 'apuestas al partido' in body or 'líneas del juego' in body)
                    d['state'] = 'EXACT_PLUS1_5_OBSERVED' if hits else 'PLUS1_5_NOT_OBSERVED_IN_DETAIL'
            except Exception as exc:
                d['state'] = 'RELATED_EVENTS_ERROR'
                d['error'] = f'{type(exc).__name__}: {exc}'
            details.append(d)

        result.update({
            'xhr_fetch_bodies_seen': len(captured),
            'xhr_bodies_with_soccer_events': source_bodies,
            'soccer_events_current_surface_all_dates': len(all_soccer),
            'soccer_events_today_current_surface': len(today_soccer),
            'soccer_today_complete_1x2': len(today_complete),
            'home_p075_candidates_today': len(home_qual),
            'exact_plus1_5_observed_today': sum(1 for d in details if d.get('state') == 'EXACT_PLUS1_5_OBSERVED'),
            'all_soccer_events': all_soccer,
            'today_soccer_events': today_soccer,
            'home_p075_candidates': home_qual,
            'candidate_contract_details': details,
            'navigation_nodes_sample': nav_nodes,
            'coverage_complete': False,
            'coverage_note': 'Counts are the current public BOSS surface captured by GetUpcomingEvents/RefreshSelectedHeader. They must not be called the entire operator universe unless a complete league traversal is independently proven.',
        })
        browser.close()

    result['decision'] = (
        'CURRENT_EXACT_PLUS1_5_CANDIDATES_OBSERVED' if result['exact_plus1_5_observed_today'] > 0
        else 'SPORTS_CANDIDATES_BUT_PLUS1_5_NOT_OBSERVED' if result['home_p075_candidates_today'] > 0
        else 'NO_HOME_P075_ON_CAPTURED_TODAY_SURFACE' if result['soccer_events_today_current_surface'] > 0
        else 'NO_TODAY_SOCCER_ON_CAPTURED_CURRENT_SURFACE'
    )
    (OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = {k: result[k] for k in (
        'captured_at_local','http','final_url','soccer_nav_clicked','xhr_fetch_bodies_seen','xhr_bodies_with_soccer_events',
        'soccer_events_current_surface_all_dates','soccer_events_today_current_surface','soccer_today_complete_1x2',
        'home_p075_candidates_today','exact_plus1_5_observed_today','decision','coverage_complete','coverage_note'
    )}
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
