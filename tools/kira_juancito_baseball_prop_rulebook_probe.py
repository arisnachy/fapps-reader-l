from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://www.juancitosport.com.do/deportes/"
OUT = Path("artifacts/kira_juancito_baseball_rulebook")
CATEGORIES = ["general", "Spreads", "Totals", "Additional Markets", "Additional Prop", "Main"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"captured_at_utc": datetime.now(timezone.utc).isoformat(), "read_only": True, "categories": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="es-DO", timezone_id="America/Santo_Domingo")
        page = ctx.new_page()
        status = None; nav_error = ""
        try:
            r = page.goto(PORTAL_URL, wait_until="commit", timeout=30000)
            status = r.status if r else None
        except PlaywrightTimeoutError as exc:
            nav_error = f"{type(exc).__name__}: {exc}"
        page.wait_for_timeout(6000)
        out["portal_http_status"] = status
        out["navigation_error"] = nav_error
        # Call the exact read-only Rule Book endpoint used by Juancito's live_ruleBook.js.
        result = page.evaluate(r"""
        async (cats) => {
          const customer = (window._CUSTOMER_INFO && window._CUSTOMER_INFO.CustomerID) || 0;
          const rows = {};
          for (const cat of cats) {
            try {
              const body = new URLSearchParams({idSport:'L-Baseball', idCategory:cat, CustomerID:String(customer)});
              const r = await fetch('/Live/proprulesAction', {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},body:body.toString(),credentials:'same-origin'});
              const text = await r.text();
              let parsed = null;
              try { parsed = JSON.parse(text); } catch (_) {}
              rows[cat] = {status:r.status, text:text.slice(0,500000), parsed};
            } catch (e) { rows[cat] = {error:String(e)}; }
          }
          return {customer_id:customer, rows};
        }
        """, CATEGORIES)
        out["customer_id"] = result.get("customer_id")
        out["categories"] = result.get("rows", {})
        browser.close()

    matches = []
    needles = ["super run", "run line", "team total", "total solo", "tie", "push", "empate", "refund", "void", "inning", "entrada", "extra inning"]
    for cat, rec in out["categories"].items():
        parsed = rec.get("parsed")
        if not isinstance(parsed, list):
            continue
        for row in parsed:
            blob = " ".join(str(row.get(k, "")) for k in row).lower()
            if any(n in blob for n in needles):
                matches.append({"category": cat, **row})
    out["matches"] = matches
    summary = {
        "portal_http_status": out.get("portal_http_status"),
        "customer_id": out.get("customer_id"),
        "category_statuses": {k:v.get("status") for k,v in out["categories"].items()},
        "parsed_counts": {k:len(v.get("parsed")) if isinstance(v.get("parsed"),list) else None for k,v in out["categories"].items()},
        "matching_rules": len(matches),
        "matching_rule_labels": [{"category":m.get("category"),"RuleID":m.get("RuleID"),"PropDescription":m.get("PropDescription")} for m in matches],
        "decision": "RULEBOOK_ROWS_CAPTURED" if matches else "NO_MATCHING_RULEBOOK_ROWS_CAPTURED"
    }
    out["summary"] = summary
    (OUT / "rulebook.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
