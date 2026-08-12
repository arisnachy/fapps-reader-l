from __future__ import annotations

import json

import kira_juancito_dual_catalog_graph_v20 as v20
import kira_juancito_dual_catalog_graph_v21 as v21


_original_apply = v20.apply


def robust_apply(page, action) -> bool:
    """Replay a board action by semantic identity, preferring stable DOM ids.

    V21 proved transport and catalog capture work, but positional nth() replay
    failed on btnMenuSports after rerender. This changes only actuator identity;
    the V20 direct and BFS algorithms, state hashes, bounds and fail-closed gates
    remain unchanged.
    """
    if action.get('kind') == 'control':
        identity = list(action.get('identity') or [])
        node_id = str(identity[0] if identity else '').strip()
        if node_id:
            try:
                result = page.evaluate(
                    """id => {
                      const nodes = [...document.querySelectorAll('[id]')].filter(e => e.id === id);
                      if (nodes.length !== 1) return {ok:false,count:nodes.length};
                      const e = nodes[0];
                      e.click();
                      return {ok:true,count:1};
                    }""",
                    node_id,
                )
                if result and result.get('ok') is True:
                    page.wait_for_timeout(650)
                    return True
            except Exception:
                pass
        # Rerender-safe fallback: resolve the full identity again, then invoke
        # the exact resolved node's id when possible. Only the legacy nth path
        # is used as final fallback and any failure still closes the graph.
        try:
            row = v20.resolve_control(page, identity)
        except Exception:
            row = None
        if row is not None:
            resolved_id = str(row.get('id') or '').strip()
            if resolved_id:
                try:
                    result = page.evaluate(
                        """id => {
                          const nodes = [...document.querySelectorAll('[id]')].filter(e => e.id === id);
                          if (nodes.length !== 1) return false;
                          nodes[0].click(); return true;
                        }""",
                        resolved_id,
                    )
                    if result is True:
                        page.wait_for_timeout(650)
                        return True
                except Exception:
                    pass
        return _original_apply(page, action)

    if action.get('kind') == 'select_option':
        identity = list(action.get('identity') or [])
        try:
            row = v20.resolve_select(page, identity)
        except Exception:
            row = None
        if row is not None:
            sid = str(row.get('id') or '').strip()
            name = str(row.get('name') or '').strip()
            try:
                if sid:
                    loc = page.locator('select').filter(has=page.locator(f'xpath=self::*[@id={json.dumps(sid)}]'))
                    # Locator.filter(has=...) is not uniformly supported for self;
                    # use CSS escaped id through evaluate when identity is stable.
                    count = page.locator(f'select[id={json.dumps(sid)}]').count()
                    target = page.locator(f'select[id={json.dumps(sid)}]').first if count == 1 else None
                elif name:
                    count = page.locator(f'select[name={json.dumps(name)}]').count()
                    target = page.locator(f'select[name={json.dumps(name)}]').first if count == 1 else None
                else:
                    target = None
                if target is not None:
                    value = str(action.get('value') or '').strip()
                    text = str(action.get('text') or '').strip()
                    if value:
                        target.select_option(value=value, timeout=5000)
                    else:
                        target.select_option(label=text, timeout=5000)
                    page.wait_for_timeout(650)
                    return True
            except Exception:
                pass
        return _original_apply(page, action)

    return False


def main() -> None:
    v20.apply = robust_apply
    # V21 owns the hardened commit-based transport bootstrap and artifact-on-
    # failure behavior. Its main then calls V20's unchanged crawlers, which now
    # resolve every replay through robust_apply above.
    v21.OUT = __import__('pathlib').Path('artifacts/kira_juancito_dual_catalog_graph_v22')
    v21.main()


if __name__ == '__main__':
    main()
