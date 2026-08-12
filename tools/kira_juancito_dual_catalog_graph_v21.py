from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

import kira_juancito_dual_catalog_graph_v20 as v20

OUT = Path('artifacts/kira_juancito_dual_catalog_graph_v21')


def board_ready(page) -> bool:
    try:
        if page.locator('#tblSH_53').count() > 0:
            return True
    except Exception:
        pass
    try:
        return any(r.get('classification') == 'SAFE_BOARD_NAV' for r in v20.board_controls(page))
    except Exception:
        return False


def navigate_root(page, nav: list[str], phase: str, *, initial: bool) -> bool:
    attempts = 5 if initial else 3
    settle_ms = 12000 if initial else 3500
    for attempt in range(1, attempts + 1):
        try:
            page.goto(v20.START, wait_until='commit', timeout=45000)
            page.wait_for_timeout(settle_ms)
            if board_ready(page):
                return True
            nav.append(f'{phase}:{attempt}:BOARD_NOT_READY:url={v20.redact_url(page.url)}')
        except Exception as exc:
            nav.append(f'{phase}:{attempt}:{type(exc).__name__}:{exc}')
        try:
            page.wait_for_timeout(1500 if initial else 500)
        except Exception:
            pass
    return False


def write_result(*, catalogs, methods, nav, direct, graph, transport_blocker: str | None = None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    dkeys = set(catalogs['direct'])
    gkeys = set(catalogs['graph'])
    only_d = sorted(dkeys - gkeys)
    only_g = sorted(gkeys - dkeys)
    dtransport = methods['direct'].get('RefreshHeaders', 0) > 0 and methods['direct'].get('GetUpcomingEvents', 0) > 0
    gtransport = methods['graph'].get('RefreshHeaders', 0) > 0 and methods['graph'].get('GetUpcomingEvents', 0) > 0
    same = bool(dkeys) and dkeys == gkeys
    complete = bool(
        transport_blocker is None
        and direct.get('complete') is True
        and graph.get('complete') is True
        and dtransport and gtransport and same
    )
    union = {**catalogs['direct'], **catalogs['graph']}
    blockers = []
    if transport_blocker:
        blockers.append({'code': transport_blocker})
    blockers.extend(direct.get('blockers') or [])
    blockers.extend(graph.get('blockers') or [])
    if dkeys and gkeys and not same:
        blockers.append({'code': 'CATALOG_SET_MISMATCH', 'only_direct': len(only_d), 'only_graph': len(only_g)})
    res = {
        'captured_at_local': datetime.now(v20.TZ).isoformat(),
        'status': 'DUAL_PUBLIC_CATALOG_COMPLETE' if complete else ('INFRA_TRANSIENT' if transport_blocker else 'DUAL_PUBLIC_CATALOG_INCOMPLETE'),
        'production_valid': complete,
        'transport_blocker': transport_blocker,
        'direct_complete': direct.get('complete') is True,
        'board_graph_complete': graph.get('complete') is True,
        'direct_transport_seen': dtransport,
        'graph_transport_seen': gtransport,
        'independent_catalog_sets_equal': same,
        'direct_event_count': len(dkeys),
        'graph_event_count': len(gkeys),
        'union_event_count': len(union),
        'only_direct': [{'header_id': h, 'event_id': e} for h, e in only_d],
        'only_graph': [{'header_id': h, 'event_id': e} for h, e in only_g],
        'direct': direct,
        'graph': graph,
        'xhr_method_counts': methods,
        'events': [union[k] for k in sorted(union)],
        'nav_errors': nav,
        'blockers': blockers,
        'negative_catalog_inference_allowed': complete,
        'guard': 'Public read-only dual discovery. V21 changes transport bootstrap/reset only; V20 catalog algorithms are reused unchanged. No wager/stake/coupon/account control is traversed.',
    }
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = {k: res[k] for k in [
        'captured_at_local', 'status', 'production_valid', 'transport_blocker',
        'direct_complete', 'board_graph_complete', 'direct_transport_seen', 'graph_transport_seen',
        'independent_catalog_sets_equal', 'direct_event_count', 'graph_event_count', 'union_event_count',
        'only_direct', 'only_graph', 'blockers'
    ]}
    summary['direct_metrics'] = {k: direct.get(k) for k in ['interactions', 'actions_seen', 'blockers']}
    summary['graph_metrics'] = {k: graph.get(k) for k in ['states_explored', 'edges_explored', 'blockers']}
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if complete else 3


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    phase = {'name': 'idle'}
    catalogs = {'direct': {}, 'graph': {}}
    methods = {'direct': {}, 'graph': {}}
    nav: list[str] = []
    direct = {'complete': False, 'interactions': 0, 'actions_seen': 0, 'blockers': []}
    graph = {'complete': False, 'states_explored': 0, 'edges_explored': 0, 'blockers': []}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1500, 'height': 1500}, locale='es-DO', timezone_id='America/Santo_Domingo')
        page = context.new_page()

        def on_response(resp):
            name = phase['name']
            if name not in catalogs or not v20.same_site(resp.url) or resp.request.resource_type not in {'xhr', 'fetch'}:
                return
            method = v20.xhr_method(resp.url)
            if method:
                methods[name][method] = methods[name].get(method, 0) + 1
            try:
                events = v20.extract_events(resp.text())
            except Exception:
                return
            for event in events:
                catalogs[name][(event['header_id'], event['event_id'])] = event

        page.on('response', on_response)

        phase['name'] = 'direct'
        if not navigate_root(page, nav, 'direct', initial=True):
            context.close(); browser.close()
            raise SystemExit(write_result(catalogs=catalogs, methods=methods, nav=nav, direct=direct, graph=graph, transport_blocker='DIRECT_ROOT_UNAVAILABLE'))
        direct = v20.direct_crawl(page)

        phase['name'] = 'graph'
        def reset_graph() -> bool:
            return navigate_root(page, nav, 'graph', initial=False)
        graph = v20.explore_graph(page, reset_graph)

        context.close(); browser.close()

    raise SystemExit(write_result(catalogs=catalogs, methods=methods, nav=nav, direct=direct, graph=graph))


if __name__ == '__main__':
    main()
