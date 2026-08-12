from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://www.juancitosport.com.do/deportes/"
OUT = Path("artifacts/kira_juancito_mlb_srl_period")
LEAGUE_LABEL = "PROPUESTAS DE MLB"
SECTION_LABEL = "PROPUESTAS DE MLB - Super Run Line"


def clean(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()


def safe_goto(page):
    err = ""; status = None
    try:
        r = page.goto(PORTAL_URL, wait_until="commit", timeout=30000)
        status = r.status if r else None
    except PlaywrightTimeoutError as exc:
        err = f"{type(exc).__name__}: {exc}"
    page.wait_for_timeout(6000)
    return status, err


def surface(page):
    for f in page.frames:
        if "BOSSWagering/Sportsbook" in (f.url or ""):
            return f
    return page


def click_exact(s, label):
    loc = s.get_by_text(label, exact=True)
    for i in range(loc.count()):
        try:
            n = loc.nth(i)
            if n.is_visible():
                n.click(force=True, timeout=6000)
                s.page.wait_for_timeout(1400)
                return True
        except Exception:
            pass
    return False


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "market": SECTION_LABEL,
        "science_status": "DO_NOT_SCORE_PERIOD_BINDING_ONLY",
    }
    responses = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="es-DO", timezone_id="America/Santo_Domingo", viewport={"width": 1440, "height": 1300})
        page = ctx.new_page()

        def on_response(resp):
            try:
                u = resp.url
                if "BOSSWagering" not in u and "juancitosport.com.do" not in u:
                    return
                ct = (resp.headers.get("content-type") or "").lower()
                if not any(x in ct for x in ("json", "text", "javascript", "html")):
                    return
                body = resp.text()
                responses.append({"url": u, "status": resp.status, "content_type": ct, "body": body[:2_000_000]})
            except Exception:
                pass

        page.on("response", on_response)
        status, err = safe_goto(page)
        s = surface(page)
        out.update({"portal_http_status": status, "navigation_error": err, "surface_url": s.url})
        out["league_clicked"] = click_exact(s, LEAGUE_LABEL)
        out["section_clicked"] = click_exact(s, SECTION_LABEL)
        page.wait_for_timeout(1800)

        binding = s.evaluate(r"""
        () => {
          const c=x=>(x||'').replace(/\s+/g,' ').trim();
          const cells=Array.from(document.querySelectorAll('[id^="PS_"]')).filter(e=>/(SRL)/i.test(c(e.closest('tr')?.innerText||'')));
          const child=[...new Set(cells.map(e=>{const m=e.id.match(/^PS_(\d+)_/);return m?Number(m[1]):null}).filter(Boolean))];
          const anchors=Array.from(document.querySelectorAll("a[onclick*='RelatedEvents(237']"));
          const parent=[...new Set(anchors.map(a=>{const m=(a.getAttribute('onclick')||'').match(/RelatedEvents\(237,\s*(\d+)/);return m?Number(m[1]):null}).filter(Boolean))];
          return {
            child_event_ids:child,
            parent_event_ids:parent,
            cells:cells.map(e=>({id:e.id,text:c(e.innerText||e.textContent),row:c(e.closest('tr')?.innerText||''),ancestor_html:(e.closest('table')?.outerHTML||'').slice(0,18000)})).slice(0,50),
            anchors:anchors.map(a=>({text:c(a.innerText||a.textContent),onclick:a.getAttribute('onclick')||'',html:(a.closest('tr')?.outerHTML||'').slice(0,12000)})).slice(0,50)
          };
        }
        """)
        out["binding"] = binding

        probes = []
        for pid in binding.get("parent_event_ids", []):
            try:
                s.evaluate(f"() => {{ if (typeof RelatedEvents === 'function') RelatedEvents(237,{int(pid)},1,0); }}")
                page.wait_for_timeout(900)
                probes.append({"parent_event_id": pid, "status": "CALLED"})
            except Exception as exc:
                probes.append({"parent_event_id": pid, "status": "ERROR", "error": f"{type(exc).__name__}: {exc}"})
        out["related_probes"] = probes

        target_ids = [str(x) for x in binding.get("parent_event_ids", []) + binding.get("child_event_ids", [])]
        rx = re.compile(r"EventStyle|IsEventNoFullTime|NoFullTime|FullTime|full.?game|period|inning|game.?type|event.?type|event.?style", re.I)
        event_network = []
        for r in responses:
            body = r.get("body", "")
            id_hit = any(t in body for t in target_ids)
            semantic_hit = bool(rx.search(body))
            if not id_hit and not semantic_hit:
                continue
            snippets = []
            positions = []
            for t in target_ids:
                pos = body.find(t)
                if pos >= 0:
                    positions.append(pos)
            for m in list(rx.finditer(body))[:40]:
                positions.append(m.start())
            for pos in sorted(set(positions))[:80]:
                snippets.append(body[max(0, pos-900):pos+1800])
            event_network.append({
                "url": r.get("url"), "status": r.get("status"), "content_type": r.get("content_type"),
                "id_hit": id_hit, "semantic_hit": semantic_hit, "snippets": snippets[:80]
            })
        out["event_network"] = event_network[:250]

        out["dom_period_candidates"] = s.evaluate(r"""
        () => {
          const c=x=>(x||'').replace(/\s+/g,' ').trim();
          const rx=/(EventStyle|IsEventNoFullTime|NoFullTime|FullTime|full.?game|period|inning|game.?type|event.?type|event.?style|SRL)/i;
          return Array.from(document.querySelectorAll('*')).map(e=>({
            tag:e.tagName,id:e.id||'',name:e.getAttribute('name')||'',type:e.getAttribute('type')||'',value:e.getAttribute('value')||'',
            cls:String(e.className||''),title:e.getAttribute('title')||'',data:Array.from(e.attributes||[]).filter(a=>a.name.startsWith('data-')).map(a=>[a.name,a.value]),
            text:c(e.innerText||e.textContent).slice(0,500),onclick:e.getAttribute('onclick')||''
          })).filter(x=>rx.test([x.id,x.name,x.value,x.cls,x.title,x.text,x.onclick,JSON.stringify(x.data)].join(' '))).slice(0,1200);
        }
        """)

        out["window_period_candidates"] = s.evaluate(r"""
        () => {
          const rx=/(event|style|period|full|inning|rule)/i; const ans=[];
          for (const k of Object.keys(window).filter(k=>rx.test(k)).slice(0,500)) {
            try {
              const v=window[k], typ=typeof v; let sample='';
              if (typ==='string'||typ==='number'||typ==='boolean') sample=String(v);
              else if (typ==='function') sample=String(v).slice(0,5000);
              else if (v && typ==='object') { try { sample=JSON.stringify(v).slice(0,10000); } catch(_){} }
              ans.push({key:k,type:typ,sample});
            } catch(_) {}
          }
          return ans;
        }
        """)

        out["script_period_candidates"] = s.evaluate(r"""
        () => {
          const rx=/(EventStyle|IsEventNoFullTime|NoFullTime|FullTime|period|inning|RelatedEvents)/i;
          return Array.from(document.scripts).map((e,i)=>({i,src:e.src||'',text:e.src?'':(e.textContent||'')})).filter(x=>rx.test(x.src+' '+x.text)).map(x=>({i:x.i,src:x.src,hits:(x.text.match(/.{0,300}(?:EventStyle|IsEventNoFullTime|NoFullTime|FullTime|period|inning|RelatedEvents).{0,700}/ig)||[]).slice(0,80)})).slice(0,200);
        }
        """)
        browser.close()

    semantic_records = sum(1 for x in out.get("event_network", []) if x.get("semantic_hit"))
    id_records = sum(1 for x in out.get("event_network", []) if x.get("id_hit"))
    summary = {
        "portal_http_status": out.get("portal_http_status"),
        "league_clicked": out.get("league_clicked"),
        "section_clicked": out.get("section_clicked"),
        "parent_event_ids": out.get("binding", {}).get("parent_event_ids", []),
        "child_event_ids": out.get("binding", {}).get("child_event_ids", []),
        "network_records_with_target_id": id_records,
        "network_records_with_period_semantics": semantic_records,
        "dom_period_candidates": len(out.get("dom_period_candidates", [])),
        "window_period_candidates": len(out.get("window_period_candidates", [])),
        "script_period_candidates": len(out.get("script_period_candidates", [])),
        "decision": "EVIDENCE_CAPTURED_REQUIRES_SEMANTIC_REVIEW" if (id_records or semantic_records) else "PERIOD_BINDING_NOT_EXPOSED",
    }
    out["summary"] = summary
    (OUT / "period_probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
