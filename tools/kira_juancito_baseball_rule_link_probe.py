from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://www.juancitosport.com.do/deportes/"
OUT = Path("artifacts/kira_juancito_baseball_rule_link")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"captured_at_utc": datetime.now(timezone.utc).isoformat(), "read_only": True}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="es-DO", timezone_id="America/Santo_Domingo")
        page = ctx.new_page()
        try:
            r = page.goto(PORTAL_URL, wait_until="commit", timeout=30000)
            out["portal_http_status"] = r.status if r else None
        except PlaywrightTimeoutError as exc:
            out["navigation_error"] = f"{type(exc).__name__}: {exc}"
        page.wait_for_timeout(6000)
        s = next((f for f in page.frames if "BOSSWagering/Sportsbook" in (f.url or "")), page)
        out["surface_url"] = s.url

        scripts = s.evaluate("Array.from(document.scripts).map(x=>x.src).filter(Boolean)")
        out["scripts"] = scripts
        js_hits = []
        for src in scripts:
            if "rule" not in src.lower() and "book" not in src.lower():
                continue
            try:
                txt = s.evaluate("async u => await (await fetch(u,{credentials:'same-origin'})).text()", src)
                if re.search(r"baseball-link|L-Baseball|baseball", txt, re.I):
                    snippets = re.findall(r".{0,1200}(?:baseball-link|L-Baseball|baseball).{0,2400}", txt, re.I | re.S)
                    js_hits.append({"src": src, "snippets": snippets[:40]})
            except Exception as exc:
                js_hits.append({"src": src, "error": f"{type(exc).__name__}: {exc}"})
        out["rule_script_hits"] = js_hits

        dom_links = s.evaluate(r"""
        () => Array.from(document.querySelectorAll('a')).map(a=>({
          text:(a.innerText||a.textContent||'').replace(/\s+/g,' ').trim(),
          href:a.href||a.getAttribute('href')||'',
          cls:String(a.className||''), id:a.id||'', target:a.target||'', onclick:a.getAttribute('onclick')||''
        })).filter(x=>/baseball|regla|rule/i.test([x.text,x.href,x.cls,x.id,x.onclick].join(' '))).slice(0,500)
        """)
        out["dom_links"] = dom_links

        # Probe any literal href revealed by the operator code/DOM. Read-only GET only.
        candidates = []
        for x in dom_links:
            if x.get("href"):
                candidates.append(x["href"])
        for h in js_hits:
            for snip in h.get("snippets", []):
                for m in re.finditer(r"https?://[^\s'\"<>]+|/[A-Za-z0-9_./?=&%-]+", snip):
                    u = m.group(0)
                    if re.search(r"baseball|regla|rule", u, re.I):
                        candidates.append(urljoin(s.url, u))
        candidates = list(dict.fromkeys(candidates))[:50]
        out["candidate_urls"] = candidates
        fetched = []
        for u in candidates:
            try:
                rec = s.evaluate(r"""async u => { const r=await fetch(u,{credentials:'same-origin'}); return {status:r.status,url:r.url,ct:r.headers.get('content-type')||'',text:(await r.text()).slice(0,1000000)}; }""", u)
                fetched.append(rec)
            except Exception as exc:
                fetched.append({"url":u,"error":f"{type(exc).__name__}: {exc}"})
        out["fetched_candidates"] = fetched
        browser.close()

    needles = re.compile(r"super\s*run\s*line|team\s*total|total\s*solo|run\s*line|push|tie|tied|refund|void|inning|entrada|extra", re.I)
    matches = []
    for rec in out.get("fetched_candidates", []):
        txt = rec.get("text", "")
        if needles.search(txt):
            snippets = [txt[max(0,m.start()-1000):m.start()+2500] for m in list(needles.finditer(txt))[:80]]
            matches.append({"url":rec.get("url"),"status":rec.get("status"),"snippets":snippets})
    out["semantic_matches"] = matches
    summary = {
        "portal_http_status": out.get("portal_http_status"),
        "surface_url": out.get("surface_url"),
        "rule_script_hits": len(out.get("rule_script_hits", [])),
        "dom_rule_links": len(out.get("dom_links", [])),
        "candidate_urls": len(out.get("candidate_urls", [])),
        "semantic_rule_pages": len(matches),
        "decision": "AUTHORITATIVE_BASEBALL_RULE_TEXT_CAPTURED" if matches else "BASEBALL_RULE_LINK_OR_TEXT_STILL_PENDING",
    }
    out["summary"] = summary
    (OUT / "rule_link_probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
