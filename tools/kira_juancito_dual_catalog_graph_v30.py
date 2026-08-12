from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

import kira_juancito_dual_catalog_graph_v20 as v20
import kira_juancito_dual_catalog_graph_v21 as v21
import kira_juancito_dual_catalog_graph_v23 as v23
import kira_juancito_dual_catalog_graph_v25 as v25
import kira_juancito_dual_catalog_graph_v26 as v26

OUT = Path('artifacts/kira_juancito_dual_catalog_graph_v30')


def install_capture(page, catalog, methods):
    def on_response(resp):
        if not v20.same_site(resp.url) or resp.request.resource_type not in {'xhr','fetch'}:
            return
        method = v20.xhr_method(resp.url)
        if method:
            methods[method] = methods.get(method, 0) + 1
        try:
            rows = v20.extract_events(resp.text())
        except Exception:
            return
        for event in rows:
            catalog[(event['header_id'], event['event_id'])] = event
    page.on('response', on_response)


def header_discoverer(browser):
    context = browser.new_context(viewport={'width':1500,'height':1500}, locale='es-DO', timezone_id='America/Santo_Domingo')
    page = context.new_page()
    catalog = {}
    methods = {}
    nav = []
    audit = []
    install_capture(page, catalog, methods)

    if not v21.navigate_root(page, nav, 'header', initial=True):
        context.close()
        return catalog, methods, {'complete':False,'headers_discovered':0,'headers_clicked':0,'rounds':0,'blockers':[{'code':'HEADER_ROOT_UNAVAILABLE'}],'audit':audit,'nav_errors':nav}

    seen = set()
    clicked = set()
    stable_rounds = 0
    rounds = 0
    blockers = []
    while stable_rounds < 3 and rounds < 5000 and not blockers:
        rounds += 1
        # Rediscover frontier from a clean root. This avoids one header click
        # collapsing/mutating the visibility of another header in the same path.
        if not v21.navigate_root(page, nav, 'header-frontier', initial=False):
            blockers.append({'code':'HEADER_RESET_FAILED'})
            break
        nodes = v26.native_headers(page)
        before = len(seen)
        for row in nodes:
            seen.add(row['id'])
        pending = sorted(seen - clicked)
        if pending:
            node_id = pending[0]
            # Each header is exercised from a freshly reset root.
            ok, error = v26.click_header(page, node_id)
            audit.append({'id':node_id,'status':'CLICKED' if ok else 'CLICK_FAILED','error':error})
            if not ok:
                blockers.append({'code':'HEADER_CLICK_FAILED','id':node_id,'error':error})
                break
            clicked.add(node_id)
            # Give all header-driven XHR a stable observation window.
            page.wait_for_timeout(1200)
            stable_rounds = 0
            continue
        stable_rounds = stable_rounds + 1 if len(seen) == before else 0
        page.wait_for_timeout(400)

    if rounds >= 5000 and stable_rounds < 3:
        blockers.append({'code':'HEADER_FIXED_POINT_BOUND_REACHED','limit':5000})
    if seen != clicked:
        blockers.append({'code':'HEADER_FRONTIER_NOT_EXHAUSTED','unvisited':sorted(seen-clicked)[:100]})
    if not seen:
        blockers.append({'code':'NO_DYNAMIC_HEADERS_DISCOVERED'})
    context.close()
    return catalog, methods, {
        'complete': not blockers,
        'headers_discovered': len(seen),
        'headers_clicked': len(clicked),
        'rounds': rounds,
        'blockers': blockers,
        'audit': audit,
        'nav_errors': nav,
    }


def graph_discoverer(browser):
    # Fresh independent context: no cache/session/DOM path from discoverer A.
    context = browser.new_context(viewport={'width':1500,'height':1500}, locale='es-DO', timezone_id='America/Santo_Domingo')
    page = context.new_page()
    catalog = {}
    methods = {}
    nav = []
    install_capture(page, catalog, methods)
    v20.apply = v23.semantic_apply
    v20.snapshot = v25.board_only_snapshot

    def reset_graph():
        return v21.navigate_root(page, nav, 'graph', initial=False)

    # Initial root is separate from A and is not trusted until reset_graph succeeds.
    if not v21.navigate_root(page, nav, 'graph-initial', initial=True):
        graph = {'complete':False,'states_explored':0,'edges_explored':0,'blockers':[{'code':'GRAPH_ROOT_UNAVAILABLE'}]}
    else:
        graph = v20.explore_graph(page, reset_graph)
    context.close()
    return catalog, methods, graph, nav


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        hcat, hmethods, hres = header_discoverer(browser)
        gcat, gmethods, graph, gnav = graph_discoverer(browser)
        browser.close()

    hkeys=set(hcat); gkeys=set(gcat)
    only_h=sorted(hkeys-gkeys); only_g=sorted(gkeys-hkeys)
    htransport=hmethods.get('RefreshHeaders',0)>0 and hmethods.get('GetUpcomingEvents',0)>0
    gtransport=gmethods.get('RefreshHeaders',0)>0 and gmethods.get('GetUpcomingEvents',0)>0
    same=bool(hkeys) and hkeys==gkeys
    complete=bool(hres.get('complete') is True and graph.get('complete') is True and htransport and gtransport and same)
    blockers=list(hres.get('blockers') or [])+list(graph.get('blockers') or [])
    if not htransport:blockers.append({'code':'HEADER_TRANSPORT_NOT_PROVED'})
    if not gtransport:blockers.append({'code':'GRAPH_TRANSPORT_NOT_PROVED'})
    if hkeys and gkeys and not same:blockers.append({'code':'CATALOG_SET_MISMATCH','only_header':len(only_h),'only_graph':len(only_g)})
    union={**hcat,**gcat}
    result={
        'captured_at_local':datetime.now(v20.TZ).isoformat(),
        'status':'DUAL_PUBLIC_CATALOG_COMPLETE' if complete else 'DUAL_PUBLIC_CATALOG_INCOMPLETE',
        'production_valid':complete,
        'fresh_contexts_independent':True,
        'header_frontier_complete':hres.get('complete') is True,
        'board_graph_complete':graph.get('complete') is True,
        'header_transport_seen':htransport,
        'graph_transport_seen':gtransport,
        'independent_catalog_sets_equal':same,
        'header_event_count':len(hkeys),
        'graph_event_count':len(gkeys),
        'union_event_count':len(union),
        'only_header':[{'header_id':h,'event_id':e} for h,e in only_h],
        'only_graph':[{'header_id':h,'event_id':e} for h,e in only_g],
        'header_metrics':{k:hres.get(k) for k in ('headers_discovered','headers_clicked','rounds','blockers')},
        'graph_metrics':{k:graph.get(k) for k in ('states_explored','edges_explored','blockers')},
        'xhr_method_counts':{'header':hmethods,'graph':gmethods},
        'events':[union[k] for k in sorted(union)],
        'blockers':blockers,
        'nav_errors':{'header':hres.get('nav_errors'),'graph':gnav},
        'negative_catalog_inference_allowed':complete,
        'independence_contract':'A=FRESH_CONTEXT_ROOT_RESET_PER_SHDR+XHR; B=SEPARATE_FRESH_CONTEXT_BOARD_BFS; BOTH_DEFER_RELATED_EVENTS_ENTRY',
    }
    (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={k:result[k] for k in ('captured_at_local','status','production_valid','fresh_contexts_independent','header_frontier_complete','board_graph_complete','header_transport_seen','graph_transport_seen','independent_catalog_sets_equal','header_event_count','graph_event_count','union_event_count','only_header','only_graph','header_metrics','graph_metrics','blockers')}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    raise SystemExit(0 if complete else 3)


if __name__=='__main__':
    main()
