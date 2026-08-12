from __future__ import annotations

import json
from pathlib import Path

import kira_euro9_tierb_p055_transport_v1 as base

OUT = Path("artifacts/kira_euro9_tierb_p055_transport_v1_gatefix")
OUT.mkdir(parents=True, exist_ok=True)
EXPECTED_DEV_LEDGER_SHA256 = "f17e823ce6bd039eb6bec116075065f9eaeb064b8ebceae203ea42a99ba83daf"
BUG_KEY = "candidate_generation_used_outcomes"


def corrected_gate(summary: dict, *, require_dev_hash: bool = False) -> tuple[bool, dict]:
    gates = dict(summary.get("gates") or {})
    outcome_flag = gates.pop(BUG_KEY, None)
    outcome_blind = outcome_flag is False
    hash_ok = True
    if require_dev_hash:
        hash_ok = summary.get("selected_ledger_sha256") == EXPECTED_DEV_LEDGER_SHA256
    audit = {
        "original_status": summary.get("status"),
        "candidate_generation_used_outcomes": outcome_flag,
        "candidate_generation_outcome_blind": outcome_blind,
        "all_substantive_gates_pass": bool(gates) and all(bool(v) for v in gates.values()),
        "dev_ledger_sha256_match": hash_ok,
        "substantive_gates": gates,
    }
    passed = audit["candidate_generation_outcome_blind"] and audit["all_substantive_gates_pass"] and hash_ok
    return passed, audit


def main() -> int:
    overall = {
        "hypothesis_id": "FOOTBALL_EURO9_FAVORITE_PLUS1_5_MULTI3_TIERB_P055_TRANSPORT_V1",
        "erratum": "prereg/FOOTBALL_EURO9_TIERB_P055_V1_GATE_BOOLEAN_ERRATUM_2026-08-12.md",
        "expected_dev_ledger_sha256": EXPECTED_DEV_LEDGER_SHA256,
        "blocks": [],
        "oos_opened": False,
    }

    dev = base.score(*base.BLOCKS[0])
    dev_pass, dev_fix = corrected_gate(dev, require_dev_hash=True)
    overall["blocks"].append({"summary": dev, "gatefix_audit": dev_fix, "corrected_status": "PASS" if dev_pass else "NO_PASS"})
    if not dev_pass:
        overall["decision"] = "DEV_GATEFIX_NO_PASS_OOS_UNOPENED"
        (OUT / "overall_summary.json").write_text(json.dumps(overall, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("KIRA_EURO9_GATEFIX", json.dumps(overall, ensure_ascii=False, sort_keys=True))
        return 0

    overall["oos_opened"] = True
    oos = base.score(*base.BLOCKS[1])
    oos_pass, oos_fix = corrected_gate(oos, require_dev_hash=False)
    overall["blocks"].append({"summary": oos, "gatefix_audit": oos_fix, "corrected_status": "PASS" if oos_pass else "NO_PASS"})
    overall["decision"] = "OOS_TRANSPORT_PASS" if oos_pass else "OOS_NO_PASS_TRANSPORT_CLOSED"
    (OUT / "overall_summary.json").write_text(json.dumps(overall, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("KIRA_EURO9_GATEFIX", json.dumps(overall, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
