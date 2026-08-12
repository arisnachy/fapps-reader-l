from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://www.juancitosport.com.do/deportes/"
OUT = Path("artifacts/kira_juancito_mlb_team_runs")
LEAGUE_LABEL = "PROPUESTAS DE MLB"
SECTION_LABEL = "PROPUESTAS DE MLB - Total solo por equipo"


def clean(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()


def safe_goto(page):
    error = ""
    status = None
    try:
        response = page.goto(PORTAL_URL, wait_until="commit", timeout=30000)
        status = response.status if response else None
    except PlaywrightTimeoutError as exc:
        error = f"{type(exc).__name__}: {exc}"
    page.wait_for_timeout(6000)
    return status, error


def sportsbook_frame(page):
    for frame in page.frames:
        if "BOSSWagering/Sportsbook" in (frame.url or ""):
            return frame
    return page


def click_exact(surface, label):
    locator = surface.get_by_text(label, exact=True)
    attempts = []
    for i in range(locator.count()):
        node = locator.nth(i)
        meta = {"index": i}
        try:
            meta.update(node.evaluate("e => ({tag:e.tagName,id:e.id||'',cls:e.className||'',role:e.getAttribute('role')||'',onclick:e.getAttribute('onclick')||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()})"))
            meta["visible"] = node.is_visible()
            if meta["visible"]:
                node.scroll_into_view_if_needed(timeout=3000)
                node.click(timeout=6000, force=True)
                meta["clicked"] = True
                attempts.append(meta)
                return True, attempts
        except Exception as exc:
            meta["error"] = f"{type(exc).__name__}: {exc}"
        attempts.append(meta)
    return False, attempts


def section_candidates(surface):
    escaped = SECTION_LABEL.replace("'", "\\'")
    return surface.evaluate(
        f"""
        () => {{
          const c=s=>(s||'').replace(/\\s+/g,' ').trim();
          const target='{escaped}';
          return Array.from(document.querySelectorAll('*')).filter(e=>c(e.innerText||e.textContent)===target).slice(0,50).map(e=>({{
            tag:e.tagName,id:e.id||'',cls:e.className||'',role:e.getAttribute('role')||'',onclick:e.getAttribute('onclick')||'',href:e.getAttribute('href')||'',
            parent_tag:e.parentElement ? e.parentElement.tagName : '',parent_id:e.parentElement ? e.parentElement.id||'' : '',parent_cls:e.parentElement ? e.parentElement.className||'' : '',
            parent_onclick:e.parentElement ? e.parentElement.getAttribute('onclick')||'' : '',text:c(e.innerText||e.textContent)
          }}));
        }}
        """
    )


def capture(surface):
    return surface.evaluate(r"""
    () => {
      const c=s=>(s||'').replace(/\s+/g,' ').trim();
      const rows=Array.from(document.querySelectorAll('tr')).map((e,i)=>({index:i,text:c(e.innerText||e.textContent),id:e.id||'',cls:e.className||''})).filter(x=>x.text).slice(0,3000);
      const cells=Array.from(document.querySelectorAll('[id]')).filter(e=>/^(SZ)?(ML|PS|TT)_\d+_/i.test(e.id||'')).map(e=>({
        id:e.id||'',text:c(e.innerText||e.textContent),title:e.getAttribute('title')||'',aria:e.getAttribute('aria-label')||'',cls:e.className||'',
        row_text:c(e.closest('tr') ? e.closest('tr').innerText || e.closest('tr').textContent : '')
      })).slice(0,6000);
      const related=Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e=>({text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''})).slice(0,1000);
      const selects=Array.from(document.querySelectorAll('select')).map((e,i)=>({
        index:i,id:e.id||'',name:e.name||'',label:e.getAttribute('aria-label')||'',title:e.getAttribute('title')||'',
        row_text:c(e.closest('tr') ? e.closest('tr').innerText || e.closest('tr').textContent : ''),
        options:Array.from(e.options||[]).map(o=>({text:c(o.textContent),value:o.value,selected:o.selected,disabled:o.disabled})).slice(0,100)
      })).slice(0,500);
      return {body:c(document.body ? document.body.innerText : '').slice(0,150000),rows,cells,related,selects};
    }
    """)


def parse_team_total_rows(snapshot):
    out=[]
    # We preserve raw exact evidence and make only conservative lexical extraction.
    for cell in snapshot.get("cells",[]):
        row=clean(cell.get("row_text"))
        text=clean(cell.get("text"))
        if not text:
            continue
        # Team total displays may use ML/PS/TT IDs differently; retain all nonempty BOSS cells after section switch.
        american=re.findall(r"(?<!\d)([+-]\d{3,4}|Even)(?!\d)",text,re.I)
        line_tokens=[]
        for token in re.findall(r"(?<!\d)([+-]?\d+(?:[½.]\d*)?)(?!\d)",text):
            normalized=token.replace('½','.5')
            try: line_tokens.append(float(normalized))
            except ValueError: pass
        out.append({"id":cell.get("id"),"text":text,"row_text":row,"american_tokens":american,"numeric_tokens":line_tokens})
    return out


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={
        "captured_at_utc":datetime.now(timezone.utc).isoformat(),
        "portal_url":PORTAL_URL,
        "league_label":LEAGUE_LABEL,
        "section_label":SECTION_LABEL,
        "read_only":True,
        "period_status":"UNKNOWN_UNTIL_AUTHORITATIVE_RULE_OR_EVENTSTYLE_BINDING",
        "science_status":"NOT_PREREGISTERED_DO_NOT_SCORE",
    }
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(locale="es-DO",timezone_id="America/Santo_Domingo",viewport={"width":1440,"height":1300})
        page=context.new_page()
        status,nav_error=safe_goto(page)
        surface=sportsbook_frame(page)
        result["portal_http_status"]=status
        result["navigation_error"]=nav_error
        result["surface_url"]=surface.url

        league_clicked,league_attempts=click_exact(surface,LEAGUE_LABEL)
        page.wait_for_timeout(1800)
        result["league_clicked"]=league_clicked
        result["league_click_attempts"]=league_attempts
        result["before_section_candidates"]=section_candidates(surface)
        result["before_section_snapshot"]=capture(surface)

        section_clicked,section_attempts=click_exact(surface,SECTION_LABEL)
        result["section_clicked"]=section_clicked
        result["section_click_attempts"]=section_attempts
        page.wait_for_timeout(2500)
        after=capture(surface)
        result["after_section_snapshot"]=after
        result["parsed_nonempty_boss_cells_after_section"]=parse_team_total_rows(after)
        browser.close()

    # Basic decision is deliberately taxonomy-only. Exact rows require visible switch + evidence.
    body=clean((result.get("after_section_snapshot") or {}).get("body"))
    result["section_visible_after_click"]=SECTION_LABEL.casefold() in body.casefold()
    result["exact_contract_rows_observed"] = len(result.get("parsed_nonempty_boss_cells_after_section",[]))
    result["decision"] = (
        "CURRENT_MLB_TEAM_RUNS_ROWS_CAPTURED_EXACT_PERIOD_PENDING"
        if result["section_clicked"] and result["exact_contract_rows_observed"] > 0
        else "MLB_TEAM_RUNS_FAMILY_CONFIRMED_DETAIL_ROWS_PENDING"
    )
    (OUT/"mlb_team_runs.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={
        "portal_http_status":result.get("portal_http_status"),
        "league_clicked":result.get("league_clicked"),
        "section_clicked":result.get("section_clicked"),
        "section_candidate_count":len(result.get("before_section_candidates",[])),
        "boss_cells_after":len((result.get("after_section_snapshot") or {}).get("cells",[])),
        "nonempty_boss_cells_after":result.get("exact_contract_rows_observed"),
        "selects_after":len((result.get("after_section_snapshot") or {}).get("selects",[])),
        "related_after":len((result.get("after_section_snapshot") or {}).get("related",[])),
        "decision":result.get("decision"),
        "period_status":result.get("period_status"),
    }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    main()
