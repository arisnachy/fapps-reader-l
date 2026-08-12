from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import kira_juancito_tennis_pregame_rule_binding_v28 as v28

OUT = Path('artifacts/kira_juancito_tennis_pregame_rule_binding_v29')
TENNIS_RE = re.compile(r'(?i)\btennis\b|\btenis\b')


def main_sport_nodes(page):
    try:
        return page.locator("[id^='Hdr'],[id^='hdr']").evaluate_all(
            r"""els=>els.map(e=>({
              id:e.id||'',
              text:(e.innerText||e.textContent||'').replace(/\s+/g,' ').trim(),
              title:e.getAttribute('title')||'',
              onclick:e.getAttribute('onclick')||''
            })).filter(x=>x.id)"""
        )
    except Exception:
        return []


def click_unique_id(page, node_id: str) -> bool:
    try:
        result = page.evaluate(
            """id=>{const xs=[...document.querySelectorAll('[id]')].filter(e=>e.id===id);if(xs.length!==1)return false;xs[0].click();return true}""",
            node_id,
        )
        if result is True:
            page.wait_for_timeout(1400)
            return True
    except Exception:
        pass
    return False


def visible_related(page):
    try:
        rows = page.locator("[onclick*='RelatedEvents']").evaluate_all(
            r"""els=>els.map(e=>({
              text:(e.innerText||e.textContent||'').replace(/\s+/g,' ').trim(),
              onclick:e.getAttribute('onclick')||''
            }))"""
        )
    except Exception:
        return []
    out = []
    for row in rows:
        m = v28.RELATED_RE.search(v28.clean(row.get('onclick')))
        if m:
            out.append({
                'header_id': int(m.group(1)),
                'event_id': int(m.group(2)),
                'title': v28.clean(row.get('text')),
                'sport': 'Tennis',
                'event_style': None,
                'identity_source': 'visible_related_under_tennis_header',
            })
    uniq = {(r['header_id'], r['event_id']): r for r in out}
    return [uniq[k] for k in sorted(uniq)]


def tennis_subheaders(page, sport_id: str):
    selector = f"#tblSH_{sport_id} [id^='shdr']"
    try:
        rows = page.locator(selector).evaluate_all(
            r"""els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\s+/g,' ').trim()})).filter(x=>x.id)"""
        )
    except Exception:
        return []
    return rows


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    observed = []
    network = []
    nav_errors = []
    discovery_audit = []
    chosen = None
    rule_clicks = []
    tennis_phase = {'active': False}

    with v28.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width':1500,'height':1400}, locale='es-DO', timezone_id='America/Santo_Domingo')
        page = ctx.new_page()

        def on_response(resp):
            if not v28.same_site(resp.url) or resp.request.resource_type not in {'xhr','fetch'}:
                return
            try:
                text = resp.text()
            except Exception:
                return
            method = v28.xhr_method(resp.url)
            for ev in v28.events(text):
                sport = v28.clean(ev.get('sport'))
                if TENNIS_RE.search(sport) or tennis_phase['active']:
                    observed.append({**ev, 'identity_source': 'boss_xhr_tennis_phase' if tennis_phase['active'] else 'boss_xhr_sport_label'})
            if re.search(r'(?i)(RuleID|RuleBook|GAME\s*-?\s*SPREAD FOR THE COMPLETE MATCH|tiebreak|tie-break|walkover|retiro|retire)', text):
                snippets = []
                for pat in (
                    r'RuleID.{0,1500}',
                    r'GAME\s*-?\s*SPREAD FOR THE COMPLETE MATCH.{0,2500}',
                    r'(?i)tiebreak.{0,1500}',
                    r'(?i)walkover.{0,1500}',
                ):
                    for m in re.finditer(pat, text, re.S):
                        snippets.append(v28.clean(m.group(0))[:3500])
                network.append({
                    'method': method,
                    'url': re.sub(r'(?i)(token|jwt|session|key)=([^&]+)', r'\1=[REDACTED]', resp.url),
                    'snippets': snippets[:20],
                })

        page.on('response', on_response)
        ok, nav_errors = v28.root(page)
        if ok:
            nodes = main_sport_nodes(page)
            tennis_nodes = [n for n in nodes if TENNIS_RE.search(' '.join(v28.clean(n.get(k)) for k in ('text','title')))]
            discovery_audit.append({'main_sport_nodes': len(nodes), 'tennis_main_nodes': tennis_nodes})
            if len(tennis_nodes) == 1:
                sport_node = tennis_nodes[0]
                tennis_phase['active'] = True
                opened = click_unique_id(page, v28.clean(sport_node['id']))
                discovery_audit.append({'sport_id': sport_node['id'], 'sport_opened': opened})
                sport_match = re.search(r'(\d+)$', v28.clean(sport_node['id']))
                sport_id = sport_match.group(1) if sport_match else ''
                if opened:
                    observed.extend(visible_related(page))
                    subs = tennis_subheaders(page, sport_id) if sport_id else []
                    discovery_audit.append({'tennis_subheader_count': len(subs), 'subheaders': subs[:100]})
                    for sub in subs:
                        sid = v28.clean(sub.get('id'))
                        clicked = click_unique_id(page, sid)
                        page.wait_for_timeout(600)
                        current = visible_related(page) if clicked else []
                        observed.extend(current)
                        discovery_audit.append({'subheader_id': sid, 'clicked': clicked, 'visible_related_after': len(current)})
                tennis_phase['active'] = False
            else:
                discovery_audit.append({'blocker': 'TENNIS_MAIN_HEADER_NOT_UNIQUE', 'count': len(tennis_nodes)})

            uniq = {}
            for ev in observed:
                try:
                    key = (int(ev['header_id']), int(ev['event_id']))
                except Exception:
                    continue
                uniq[key] = ev
            candidates = sorted(
                uniq.values(),
                key=lambda e: (0 if e.get('event_style') == 10 else 1, int(e['event_id']))
            )
            if candidates:
                chosen = candidates[0]
                try:
                    called = page.evaluate(
                        "([h,e])=>{if(typeof RelatedEvents!=='function')return false;RelatedEvents(h,e,1,0);return true}",
                        [chosen['header_id'], chosen['event_id']],
                    )
                    page.wait_for_timeout(1800)
                except Exception:
                    called = False
                if called:
                    controls = v28.safe_rule_controls(page)
                    for row in controls[:80]:
                        clicked = v28.click_unique_rule(page, row)
                        if clicked:
                            page.wait_for_timeout(1200)
                        after = v28.clean(page.locator('body').inner_text())[:50000]
                        hit = bool(re.search(
                            r'(?i)Rule\s*234|RuleID\s*234|GAME\s*-?\s*SPREAD FOR THE COMPLETE MATCH|Handicap del Juego para\s+el partido completo',
                            after,
                        ))
                        rule_clicks.append({
                            'id': v28.clean(row.get('id')),
                            'text': v28.clean(row.get('text')),
                            'title': v28.clean(row.get('title')),
                            'onclick': v28.clean(row.get('onclick')),
                            'clicked': clicked,
                            'rule234_text_seen_after': hit,
                            'body_after_excerpt': after[:12000] if hit else '',
                        })
                        try:
                            page.evaluate("([h,e])=>RelatedEvents(h,e,1,0)", [chosen['header_id'], chosen['event_id']])
                            page.wait_for_timeout(700)
                        except Exception:
                            pass
        ctx.close()
        browser.close()

    binding_hits = [x for x in rule_clicks if x.get('rule234_text_seen_after')]
    network234 = [
        x for x in network
        if any(re.search(r'(?i)(RuleID\s*234|GAME\s*-?\s*SPREAD FOR THE COMPLETE MATCH)', s) for s in x.get('snippets') or [])
    ]
    binding = bool(chosen and (binding_hits or network234))
    unique_events = {(int(e['header_id']), int(e['event_id'])) for e in observed if str(e.get('header_id','')).isdigit() and str(e.get('event_id','')).isdigit()}
    result = {
        'captured_at_local': datetime.now(v28.TZ).isoformat(),
        'status': 'PREGAME_RULE234_BINDING_PASS' if binding else ('PREGAME_RULE234_BINDING_NOT_PROVED' if chosen else 'TENNIS_DISCOVERY_INCOMPLETE'),
        'production_valid_binding': binding,
        'chosen_event': chosen,
        'tennis_events_observed': len(unique_events),
        'safe_rule_controls_tried': len(rule_clicks),
        'binding_hits': binding_hits,
        'network_rule234_hits': network234,
        'nav_errors': nav_errors,
        'discovery_audit': discovery_audit,
        'rule_click_audit': rule_clicks,
        'safety': 'Read-only. Sport/header and RelatedEvents navigation plus uniquely identified Rule/Regla/Help/Info controls only; bet cells/coupon/stake/account controls excluded.',
        'holdout_scored': False,
        'v29_fix': 'MAIN_SPORT_HDR_THEN_TBL_SH_SUBHEADERS_PLUS_TENNIS_OR_TENIS_LABEL',
    }
    (OUT/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('captured_at_local','status','production_valid_binding','chosen_event','tennis_events_observed','safe_rule_controls_tried','nav_errors','discovery_audit')}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if binding else 3)


if __name__ == '__main__':
    run()
