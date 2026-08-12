from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://www.juancitosport.com.do/deportes/"
OUT = Path("artifacts/kira_juancito_mlb_srl")
LEAGUE_LABEL = "PROPUESTAS DE MLB"
SECTION_LABEL = "PROPUESTAS DE MLB - Super Run Line"


def clean(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()


def safe_goto(page):
    err=""; status=None
    try:
        r=page.goto(PORTAL_URL,wait_until="commit",timeout=30000)
        status=r.status if r else None
    except PlaywrightTimeoutError as exc:
        err=f"{type(exc).__name__}: {exc}"
    page.wait_for_timeout(6000)
    return status,err


def sportsbook_frame(page):
    for f in page.frames:
        if "BOSSWagering/Sportsbook" in (f.url or ""):
            return f
    return page


def click_exact(surface,label):
    loc=surface.get_by_text(label,exact=True)
    attempts=[]
    for i in range(loc.count()):
        n=loc.nth(i); meta={"index":i}
        try:
            meta.update(n.evaluate("e=>({tag:e.tagName,id:e.id||'',cls:e.className||'',onclick:e.getAttribute('onclick')||'',text:(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim()})"))
            meta["visible"]=n.is_visible()
            if meta["visible"]:
                n.scroll_into_view_if_needed(timeout=3000)
                n.click(force=True,timeout=6000)
                attempts.append({**meta,"clicked":True})
                return True,attempts
        except Exception as exc:
            meta["error"]=f"{type(exc).__name__}: {exc}"
        attempts.append(meta)
    return False,attempts


def capture(surface):
    return surface.evaluate(r"""
    () => {
      const c=s=>(s||'').replace(/\s+/g,' ').trim();
      return {
        body:c(document.body?document.body.innerText:'').slice(0,150000),
        cells:Array.from(document.querySelectorAll('[id]')).filter(e=>/^(SZ)?(ML|PS|TT)_\d+_/i.test(e.id||'')).map(e=>({
          id:e.id||'',text:c(e.innerText||e.textContent),title:e.getAttribute('title')||'',aria:e.getAttribute('aria-label')||'',cls:e.className||'',
          row_text:c(e.closest('tr') ? e.closest('tr').innerText || e.closest('tr').textContent : ''),
          row_id:e.closest('tr') ? (e.closest('tr').id||'') : '',
          row_cls:e.closest('tr') ? (e.closest('tr').className||'') : ''
        })).slice(0,8000),
        related:Array.from(document.querySelectorAll("a[onclick*='RelatedEvents']")).map(e=>({text:c(e.innerText||e.textContent),onclick:e.getAttribute('onclick')||''})).slice(0,1500),
        rows:Array.from(document.querySelectorAll('tr')).map((e,i)=>({index:i,id:e.id||'',cls:e.className||'',text:c(e.innerText||e.textContent),html:(e.outerHTML||'').slice(0,12000)})).filter(x=>x.text).slice(0,4000)
      };
    }
    """)


def parse_line_price(text):
    t=clean(text).replace('½','.5').replace('−','-')
    m=re.search(r'([+-]\d+(?:\.5)?)\s+([+-]\d{3,4}|Even)',t,re.I)
    return (float(m.group(1)),m.group(2)) if m else (None,None)


def parse_srl(snapshot):
    parsed=[]
    for cell in snapshot.get('cells',[]):
        cid=str(cell.get('id') or '')
        row=clean(cell.get('row_text'))
        if not re.match(r'^(?:SZ)?PS_',cid,re.I) or '(SRL)' not in row.upper():
            continue
        text=clean(cell.get('text'))
        if not text: continue
        line,price=parse_line_price(text)
        idm=re.match(r'^(?:SZ)?PS_(\d+)_([123])$',cid,re.I)
        participant=re.sub(r'\s*\(SRL\).*$', '', row, flags=re.I).strip()
        parsed.append({
          'cell_id':cid,'cell_event_id':int(idm.group(1)) if idm else None,'selection_code':int(idm.group(2)) if idm else None,
          'participant':participant,'text':text,'line':line,'american_price':price,'row_text':row,
          'row_id':cell.get('row_id'),'row_cls':cell.get('row_cls'),'actionable':'tooltip_addBet' in str(cell.get('cls') or '') and 'cellCandado' not in str(cell.get('cls') or '')
        })
    return parsed


def capture_event_info(surface, cell_ids):
    return surface.evaluate(r"""
    (cellIds) => {
      const safe = v => (v === undefined ? null : v);
      const out=[];
      for (const cid of cellIds) {
        const e=document.getElementById(cid);
        const m=(cid||'').match(/^(?:SZ)?PS_(\d+)_([123])$/i);
        if (!e || !m) { out.push({cell_id:cid,error:'CELL_OR_ID_MISSING'}); continue; }
        const eventId=parseInt(m[1],10);
        const headers=[];
        let n=e;
        for (let i=0;i<8 && n;i++,n=n.parentElement) {
          for (const k of ['headerId','HeaderId','headerID']) {
            try { if (n[k] !== undefined && n[k] !== null && String(n[k]) !== '') headers.push(n[k]); } catch (_) {}
          }
          for (const a of ['headerId','headerid','header-id','data-header-id']) {
            try { const v=n.getAttribute && n.getAttribute(a); if (v) headers.push(v); } catch (_) {}
          }
        }
        const uniq=[...new Set(headers.map(String))];
        let info=null, usedHeader=null, err='';
        for (const h of uniq) {
          try {
            if (window.WagerSession && typeof WagerSession.SearchEventInfo === 'function') {
              const x=WagerSession.SearchEventInfo(h,eventId);
              if (x) { info=x; usedHeader=h; break; }
            }
          } catch (ex) { err=String(ex); }
        }
        if (!info) {
          out.push({cell_id:cid,event_id:eventId,header_candidates:uniq,header_id:usedHeader,error:err||'EVENT_INFO_NOT_FOUND'});continue;
        }
        const scalar={};
        for (const k of Object.keys(info).slice(0,120)) {
          try {
            const v=info[k];
            if (v===null || ['string','number','boolean'].includes(typeof v)) scalar[k]=safe(v);
          } catch (_) {}
        }
        out.push({cell_id:cid,event_id:eventId,header_candidates:uniq,header_id:usedHeader,
          Style:safe(info.Style),EventStyle:safe(info.EventStyle),IsEventNoFullTime:safe(info.IsEventNoFullTime),
          EventNoFullTime:safe(info.EventNoFullTime),Description:safe(info.Description),Period:safe(info.Period),scalar_fields:scalar});
      }
      return out;
    }
    """, cell_ids)


def period_evidence_from_network(records, base_ids, cell_ids):
    keys=[str(x) for x in sorted(set(base_ids)|set(cell_ids))]
    out=[]
    for r in records:
        body=r.get('body','')
        if not body or not any(k in body for k in keys): continue
        if not re.search(r'EventStyle|IsEventNoFullTime|NoFullTime|FullTime',body,re.I): continue
        snippets=[]
        for k in keys:
            pos=body.find(k)
            if pos>=0: snippets.append(body[max(0,pos-600):pos+1200])
        out.append({'url':r.get('url'),'status':r.get('status'),'snippets':snippets[:6]})
    return out


def classify_period(event_infos, network_evidence):
    explicit=[]
    for x in event_infos:
        es=x.get('EventStyle'); nf=x.get('IsEventNoFullTime')
        if es is not None or nf is not None:
            explicit.append(x)
    if explicit:
        # Authoritative source contract: EventStyle=10 and/or explicit IsEventNoFullTime=false is full-game evidence;
        # any contrary explicit flag/style rejects full-game rather than guessing.
        ok=True
        for x in explicit:
            es=x.get('EventStyle'); nf=x.get('IsEventNoFullTime')
            if nf is True: ok=False
            if es is not None and es != 10: ok=False
        if ok: return 'AUTHORITATIVE_FULL_GAME_EVENTINFO', explicit
        return 'AUTHORITATIVE_NON_FULL_GAME_OR_CONFLICT', explicit
    if network_evidence: return 'AUTHORITATIVE_PERIOD_EVIDENCE_NETWORK_REVIEW', network_evidence
    # Style alone is preserved but not silently equated to EventStyle.
    style_rows=[x for x in event_infos if x.get('Style') is not None]
    if style_rows: return 'STYLE_CAPTURED_EVENTSTYLE_BINDING_PENDING', style_rows
    return 'PERIOD_EVIDENCE_PENDING', []


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={"captured_at_utc":datetime.now(timezone.utc).isoformat(),"read_only":True,"section_label":SECTION_LABEL,"science_status":"NOT_PREREGISTERED_DO_NOT_SCORE"}
    network=[]
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True)
        ctx=b.new_context(locale='es-DO',timezone_id='America/Santo_Domingo',viewport={'width':1440,'height':1300})
        page=ctx.new_page()
        def on_response(resp):
            try:
                u=resp.url
                if 'BOSSWagering' not in u and 'livev2.juancitosport.com.do' not in u: return
                ctype=(resp.headers.get('content-type') or '').lower()
                if not any(x in ctype for x in ('json','text','javascript','html')): return
                txt=resp.text(); txt=txt[:2_000_000]
                network.append({'url':u,'status':resp.status,'content_type':ctype,'body':txt})
            except Exception: pass
        page.on('response',on_response)
        status,err=safe_goto(page); s=sportsbook_frame(page)
        result.update({'portal_http_status':status,'navigation_error':err,'surface_url':s.url})
        result['league_clicked'],result['league_click_attempts']=click_exact(s,LEAGUE_LABEL)
        page.wait_for_timeout(1200)
        result['section_clicked'],result['section_click_attempts']=click_exact(s,SECTION_LABEL)
        page.wait_for_timeout(2500)
        snap=capture(s); result['snapshot']=snap; parsed=parse_srl(snap); result['parsed_srl_rows']=parsed
        result['event_info_rows']=capture_event_info(s,[r['cell_id'] for r in parsed])
        parents=[]
        for x in snap.get('related',[]):
            m=re.search(r'RelatedEvents\(237,\s*(\d+),\s*1,\s*0\)',x.get('onclick',''))
            if m and int(m.group(1)) not in parents: parents.append(int(m.group(1)))
        result['srl_parent_event_ids']=parents
        related_probes=[]
        for pid in parents:
            try:
                s.evaluate(f"() => {{ if (typeof RelatedEvents === 'function') RelatedEvents(237,{pid},1,0); }}")
                page.wait_for_timeout(600); related_probes.append({'parent_event_id':pid,'status':'CALLED'})
            except Exception as exc: related_probes.append({'parent_event_id':pid,'status':'ERROR','error':f'{type(exc).__name__}: {exc}'})
        result['related_probes']=related_probes
        result['network_period_evidence']=period_evidence_from_network(network,parents,[r['cell_event_id'] for r in parsed if r.get('cell_event_id')])
        result['network_response_count']=len(network)
        b.close()
    valid=[r for r in result['parsed_srl_rows'] if r['line'] is not None and r['american_price'] is not None and r['actionable']]
    period_status,period_rows=classify_period(result.get('event_info_rows',[]),result.get('network_period_evidence',[]))
    result['period_status']=period_status; result['period_evidence_rows']=period_rows
    if not valid: decision='SRL_DETAIL_ROWS_PENDING'
    elif period_status=='AUTHORITATIVE_FULL_GAME_EVENTINFO': decision='CURRENT_SRL_EXACT_ROWS_FULL_GAME_EVIDENCE_FOUND'
    elif period_status=='AUTHORITATIVE_NON_FULL_GAME_OR_CONFLICT': decision='CURRENT_SRL_EXACT_ROWS_PERIOD_REJECTED'
    else: decision='CURRENT_SRL_EXACT_ROWS_PERIOD_PENDING'
    result['decision']=decision
    (OUT/'srl.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines={}; participants=[]
    for r in valid:
        lines[str(r['line'])]=lines.get(str(r['line']),0)+1; participants.append({'event_id':r['cell_event_id'],'participant':r['participant'],'line':r['line'],'american_price':r['american_price'],'actionable':r['actionable']})
    summary={'portal_http_status':result.get('portal_http_status'),'league_clicked':result.get('league_clicked'),'section_clicked':result.get('section_clicked'),'exact_srl_rows':len(valid),'line_counts':lines,'unique_srl_parent_events':len(result.get('srl_parent_event_ids',[])),'period_status':period_status,'event_info_rows':result.get('event_info_rows',[]),'participants':participants,'decision':decision}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
