from __future__ import annotations

from pathlib import Path

import kira_juancito_dual_catalog_graph_v20 as v20
import kira_juancito_dual_catalog_graph_v21 as v21
import kira_juancito_dual_catalog_graph_v23 as v23
import kira_juancito_dual_catalog_graph_v24 as v24


_BASE_SNAPSHOT = v24.snapshot_without_selected_option_noops


def board_only_snapshot(page):
    """Keep catalog discovery on the board plane; defer event entry to event graphs.

    `RelatedEvents(header_id,event_id)` is positive event identity evidence and stays
    in the structural snapshot / XHR catalog. It is not a board-navigation edge:
    FULLVIS certifies the reachable market surface of every reconciled exact event
    separately on public + authenticated planes. Traversing every RelatedEvents entry
    here duplicates the exact-event graph and creates artificial O(N_events) fanout.

    This filter removes only control actions whose exact onclick is RelatedEvents(...).
    No event identity, visible_related record, XHR response, sport/league/filter control,
    select option, state hash, graph bound or fail-closed condition is removed.
    """
    snap = _BASE_SNAPSHOT(page)
    filtered = []
    deferred = 0
    for action in snap.get("actions") or []:
        if action.get("kind") != "control":
            filtered.append(action)
            continue
        identity = list(action.get("identity") or [])
        onclick = v20.clean(identity[5] if len(identity) > 5 else "")
        if v20.RELATED_RE.search(onclick):
            deferred += 1
            continue
        filtered.append(action)

    snap["actions"] = filtered
    counts = dict(snap.get("surface_counts") or {})
    counts["deferred_exact_event_surface_entries"] = deferred
    snap["surface_counts"] = counts
    return snap


def main() -> None:
    v20.apply = v23.semantic_apply
    v20.snapshot = board_only_snapshot
    v21.OUT = Path("artifacts/kira_juancito_dual_catalog_graph_v25")
    v21.main()


if __name__ == "__main__":
    main()
