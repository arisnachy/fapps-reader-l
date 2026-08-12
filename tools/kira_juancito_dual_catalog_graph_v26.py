from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

import kira_juancito_dual_catalog_graph_v20 as v20
import kira_juancito_dual_catalog_graph_v21 as v21
import kira_juancito_dual_catalog_graph_v23 as v23
import kira_juancito_dual_catalog_graph_v25 as v25

OUT = Path('artifacts/kira_juancito_dual_catalog_graph_v26')


def native_headers(page):
    try:
        rows = page.locator("[id^='shdr']").evaluate_all(
            """els=>els.map(e=>({id:e.id||'',text:(e.innerText||e.textContent||'').replace(/\s+/g,' ').trim(),onclick:e.getAttribute('onclick')||''}))"""
        )
    except Exception:
        return []
    out = []
    seen = set()
    for row in rows:
        node_id = v20.clean(row.get('id'))
        if node_id and node_id not in seen:
            seen.add(node_id)
            out.append({'id': node_id, 'text': v20.clean(row.get('text')), 'onclick': v20.clean(row.get('onclick'))})
    return out


def click_header(page, node_id: str):
    try:
        result = page.evaluate(
            """id=>{const nodes=[...document.querySelectorAll('[id]')].filter(e=>e.id===id);if(nodes.length!==1)return {ok:false,count:nodes.length};nodes[0].click();return {ok:true,count:1}}""",
            node_id,
        )
        if not result or result.get('ok') is not True:
            return False, f"IDENTITY_NOT_UNIQUE count={result.get('count') if result else 'none'}"
        page.wait_for_timeout(700)
        return True, ''
    except Exception as exc:
        return False, f'{type(exc).__name__}: {exc}'


def enumerate_headers(page):
    seen = set()
    clicked = set()
    audit = []
    stable = 0
    rounds = 0
    blockers = []
    while stable < 3 and rounds < 5000 and not blockers:
        rounds += 1
        before = len(seen)
        for row in native_headers(page):
            seen.add(row['id'])
        pending = sorted(seen - clicked)
        if pending:
            node_id = pending[0]
            ok, error = click_header(page, node_id)
            audit.append({'id': node_id, 'status': 'CLICKED' if ok else 'CLICK_FAILED', 'error': error})
            if not ok:
                blockers.append({'code': 'HEADER_CLICK_FAILED', 'id': node_id, 'error': error})
                break
            clicked.add(node_id)
            stable = 0
            continue
        stable = stable + 1 if len(seen) == before else 0
        page.wait_for_timeout(450)
    if rounds >= 5000 and stable < 3:
        blockers.append({'code': 'HEADER_FIXED_POINT_BOUND_REACHED', 'limit': 5000})
    if seen != clicked:
        blockers.append({'code': 'HEADER_FRONTIER_NOT_EXHAUSTED', 'unvisited': sorted(seen-clicked)[:100]})
    if not seen:
        blockers.append({'code': 'NO_DYNAMIC_HEADERS_DISCOVERED'})
    return {'complete': not blockers, 'headers_discovered': len(seen), 'headers_clicked': len(clicked), 'rounds': rounds, 'audit': audit, 'blockers': blockers}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    catalogs = {'header': {}, 'graph': {}}
    methods = {'header': {}, 'graph': {}}
    phase = {'name': 'idle'}
    nav = []
    header_result = {'complete': False, 'blockers': []}
    graph = {'complete': False, 'states_explored': 0, 'edges_explored': 0, 'blockers': []}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width':1500,'height':1500}, locale='es-DO', timezone_id='America/Santo_Domingo')
        page = context.new_page()

        def on_response(resp):
            name = phase['name']
            if name not in catalogs or not v20.same_site(resp.url) or resp.request.resource_type not in {'xhr','fetch'}:
                return
            method = v20.xhr_method(resp.url)
            if method:
                methods[name][method] = methods[name].get(method, 0) + 1
            try:
                events = v20.extract_events(resp.text())
            except Exception:
                return
            for event in events:
                catalogs[name][(event['header_id'],event['event_id'])] = event

        page.on('response', on_response)

        # Discoverer A: no BFS, no event entry. Native shdr* fixed point + BOSS XHR.
        phase['name'] = 'header'
        if not v21.navigate_root(page, nav, 'header', initial=True):
            header_result = {'complete': False, 'headers_discovered':0, 'headers_clicked':0, 'rounds':0, 'audit':[], 'blockers':[{'code':'HEADER_ROOT_UNAVAILABLE'}]}
        else:
            header_result = enumerate_headers(page)

        # Discoverer B: independent reset/replay board state graph; exact events are
        # identities in state/XHR evidence but RelatedEvents entry is deferred.
        phase['name'] = 'graph'
        v20.apply = v23.semantic_apply
        v20.snapshot = v25.board_only_snapshot
        def reset_graph():
            return v21.navigate_root(page, nav, 'graph', initial=False)
        graph = v20.explore_graph(page, reset_graph)

        context.close(); browser.close()

    hkeys = set(catalogs['header'])
    gkeys = set(catalogs['graph'])
    only_h = sorted(hkeys-gkeys)
    only_g = sorted(gkeys-hkeys)
    htransport = methods['header'].get('RefreshHeaders',0)>0 and methods['header'].get('GetUpcomingEvents',0)>0
    gtransport = methods['graph'].get('RefreshHeaders',0)>0 and methods['graph'].get('GetUpcomingEvents',0)>0
    same = bool(hkeys) and hkeys == gkeys
    complete = bool(header_result.get('complete') is True and graph.get('complete') is True and htransport and gtransport and same)
    union = {**catalogs['header'], **catalogs['graph']}
    blockers = list(header_result.get('blockers') or []) + list(graph.get('blockers') or [])
    if not htransport: blockers.append({'code':'HEADER_TRANSPORT_NOT_PROVED'})
    if not gtransport: blockers.append({'code':'GRAPH_TRANSPORT_NOT_PROVED'})
    if hkeys and gkeys and not same: blockers.append({'code':'CATALOG_SET_MISMATCH','only_header':len(only_h),'only_graph':len(only_g)})
    if not hkeys: blockers.append({'code':'HEADER_CATALOG_EMPTY'})
    if not gkeys: blockers.append({'code':'GRAPH_CATALOG_EMPTY'})

    result = {
        'captured_at_local': datetime.now(v20.TZ).isoformat(),
        'status': 'DUAL_PUBLIC_CATALOG_COMPLETE' if complete else 'DUAL_PUBLIC_CATALOG_INCOMPLETE',
        'production_valid': complete,
        'header_frontier_complete': header_result.get('complete') is True,
        'board_graph_complete': graph.get('complete') is True,
        'header_transport_seen': htransport,
        'graph_transport_seen': gtransport,
        'independent_catalog_sets_equal': same,
        'header_event_count': len(hkeys),
        'graph_event_count': len(gkeys),
        'union_event_count': len(union),
        'only_header': [{'header_id':h,'event_id':e} for h,e in only_h],
        'only_graph': [{'header_id':h,'event_id':e} for h,e in only_g],
        'header_metrics': {k:header_result.get(k) for k in ('headers_discovered','headers_clicked','rounds','blockers')},
        'graph_metrics': {k:graph.get(k) for k in ('states_explored','edges_explored','blockers')},
        'xhr_method_counts': methods,
        'events': [union[k] for k in sorted(union)],
        'blockers': blockers,
        'nav_errors': nav,
        'negative_catalog_inference_allowed': complete,
        'independence_contract': 'A=NATIVE_SHDR_FIXED_POINT_PLUS_XHR_NO_BFS; B=BOARD_STATE_BFS_WITH_CROSS_COMBINATIONS; BOTH_DEFER_EXACT_EVENT_ENTRY',
        'guard': 'No RelatedEvents entry/wager/stake/coupon/account mutation. Exact event surfaces are certified separately after catalog reconciliation.'
    }
    (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    summary = {k:result[k] for k in ('captured_at_local','status','production_valid','header_frontier_complete','board_graph_complete','header_transport_seen','graph_transport_seen','independent_catalog_sets_equal','header_event_count','graph_event_count','union_event_count','only_header','only_graph','header_metrics','graph_metrics','blockers')}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    raise SystemExit(0 if complete else 3)


if __name__ == '__main__':
    main()
