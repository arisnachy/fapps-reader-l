from __future__ import annotations

from pathlib import Path

import kira_juancito_dual_catalog_graph_v20 as v20
import kira_juancito_dual_catalog_graph_v21 as v21
import kira_juancito_dual_catalog_graph_v23 as v23


_ORIGINAL_SNAPSHOT = v20.snapshot


def snapshot_without_selected_option_noops(page):
    """Preserve FULLVIS actions except select_option transitions proven to be no-ops.

    A select_option action is suppressed only when its exact select identity resolves
    to the currently selected value/text in the same stable DOM state. Re-selecting
    the already-selected option cannot expose a new reachable state, so excluding it
    preserves all cross-control combinations while preventing artificial edge growth.
    """
    snap = _ORIGINAL_SNAPSHOT(page)
    safe_selects, _ = v20.board_selects(page)

    selected_by_identity: dict[tuple[str, ...], set[tuple[str, str]]] = {}
    for row in safe_selects:
        ident = tuple(v20.select_identity(row))
        selected: set[tuple[str, str]] = set()
        current_value = v20.clean(row.get("value"))
        for option in row.get("options") or []:
            if bool(option.get("selected")):
                selected.add((v20.clean(option.get("value")), v20.clean(option.get("text"))))
        if current_value:
            selected.add((current_value, ""))
        selected_by_identity[ident] = selected

    filtered = []
    suppressed = 0
    for action in snap.get("actions") or []:
        if action.get("kind") != "select_option":
            filtered.append(action)
            continue

        ident = tuple(action.get("identity") or [])
        value = v20.clean(action.get("value"))
        text = v20.clean(action.get("text"))
        selected = selected_by_identity.get(ident, set())
        is_current = (value, text) in selected or (bool(value) and (value, "") in selected)
        if is_current:
            suppressed += 1
            continue
        filtered.append(action)

    snap["actions"] = filtered
    counts = dict(snap.get("surface_counts") or {})
    counts["suppressed_current_select_noops"] = suppressed
    snap["surface_counts"] = counts
    return snap


def main() -> None:
    # V23 semantic replay remains authoritative for id-less controls.
    v20.apply = v23.semantic_apply
    # V24 changes only action generation by removing transitions proven to leave
    # the select at its already-selected option. No graph limits are increased.
    v20.snapshot = snapshot_without_selected_option_noops
    v21.OUT = Path("artifacts/kira_juancito_dual_catalog_graph_v24")
    v21.main()


if __name__ == "__main__":
    main()
