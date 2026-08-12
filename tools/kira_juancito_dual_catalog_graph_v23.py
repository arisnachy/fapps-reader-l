from __future__ import annotations

import kira_juancito_dual_catalog_graph_v20 as v20
import kira_juancito_dual_catalog_graph_v21 as v21
import kira_juancito_dual_catalog_graph_v22 as v22


def semantic_apply(page, action) -> bool:
    if action.get('kind') == 'control':
        identity = list(action.get('identity') or [])
        node_id = str(identity[0] if len(identity) > 0 else '').strip()
        class_name = str(identity[4] if len(identity) > 4 else '').strip()
        onclick = str(identity[5] if len(identity) > 5 else '').strip()

        # First keep V22's stable-id path.
        if node_id:
            return v22.robust_apply(page, action)

        # Id-less BOSS multi-header controls are stable by exact class+onclick.
        # Never fall back to positional selection when this identity is present.
        if onclick:
            try:
                result = page.evaluate(
                    """([cls,onclick]) => {
                      const nodes = [...document.querySelectorAll('[onclick]')].filter(e => {
                        const ec = typeof e.className === 'string' ? e.className : '';
                        return (e.getAttribute('onclick')||'').trim() === onclick.trim()
                          && (!cls || ec.trim() === cls.trim());
                      });
                      if (nodes.length !== 1) return {ok:false,count:nodes.length};
                      nodes[0].click(); return {ok:true,count:1};
                    }""",
                    [class_name, onclick],
                )
                if result and result.get('ok') is True:
                    page.wait_for_timeout(650)
                    return True
                return False
            except Exception:
                return False

        # With neither id nor onclick, V22 remains fail-closed through its full
        # identity resolver; no new positional shortcut is introduced here.
        return v22.robust_apply(page, action)

    return v22.robust_apply(page, action)


def main() -> None:
    v20.apply = semantic_apply
    v21.OUT = __import__('pathlib').Path('artifacts/kira_juancito_dual_catalog_graph_v23')
    v21.main()


if __name__ == '__main__':
    main()
