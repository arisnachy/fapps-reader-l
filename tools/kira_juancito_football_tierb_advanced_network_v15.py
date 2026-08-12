from __future__ import annotations
import json,re,urllib.parse
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_tierb_advanced_network_v15');TZ=ZoneInfo('America/Santo_Domingo')
TARGETS=[(2037,1961877,'Shandong Luneng Taishan',1),(2015,1962330,'Ruch Chorzow',2),(2059,1959023,'LASK Linz',3)]
def safe_url(u):
 try:
  z=urllib.parse.urlsplit(u);return urllib.parse.urlunsplit((z.scheme,z.netloc,z.path,'',''))
 except Exception:return ''
def sanitize(s):
 s=re.sub(r'(?i)(token|authorization|jwt|session|cookie)["\'\s:=]+[A-Za-z0-9._~+/=-]{8,}',r'\1=[REDACTED]',s)
 s=re.sub(r'https?://[^\s"\']+\?[^\s"\']+',lambda m:safe_url(m.group(0)),s)
 s=re.sub(r'\b[A-Za-z0-9_-]{36,}\b','[REDACTED_LONG_TOKEN]',s)
 return re.sub(r'\s+',' ',s).strip()
def snippets(text,team):
 pats=[re.escape(team),r'team\s*total',r'team\s*goals',r'handicap',r'alternative',r'double\s*chance',r'draw\s*no\s*bet',r'\+?1[\.,]5']
 out=[];seen=set()
 for pat in pats:
  for m in re.finditer(pat,text,re.I):
   a=max(0,m.start()-600);z=min(len(text),m.end()+1000);s=sanitize(text[a:z])
   if s and s not in seen:seen.add(s);out.append({'pattern':pat,'snippet':s[:2200]})
   if len(out)>=80:return out
 return out
def main():
 OUT.mkdir(parents=True,exist_ok=True);nav=[];results=[]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':1600,'height':1800},locale='es-DO',timezone_id='America/Santo_Domingo')
  loaded=False
  for a in range(4):
   try:
    p.goto(START,wait_until='commit',timeout=45000);p.wait_for_timeout(10000)
    if p.locator('#tblSH_53').count():loaded=True;break
   except Exception as ex:nav.append(f'{a+1}:{type(ex).__name__}:{ex}')
  if not loaded:b.close();raise RuntimeError('BOSS unavailable: '+' | '.join(nav))
  for h,e,team,rank in TARGETS:
   rec={'event_id':e,'selected_team':team,'tierb_rank':rank,'responses':[]};caps=[]
   def onr(r):
    u=r.url.lower()
    if 'digitalsportstech' not in u and 'dst' not in u:return
    try:body=r.text()
    except Exception:return
    if len(body)>4_000_000:body=body[:4_000_000]
    ss=snippets(body,team)
    caps.append({'url_path':safe_url(r.url),'status':r.status,'content_type':r.headers.get('content-type',''),'bytes_scanned':len(body),'keyword_snippets':ss})
   p.on('response',onr)
   try:
    p.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[h,e]);p.wait_for_timeout(18000)
   except Exception as ex:rec['related_error']=f'{type(ex).__name__}:{ex}'
   try:p.remove_listener('response',onr)
   except Exception:pass
   rec['responses']=caps; rec['responses_with_keyword_snippets']=sum(bool(x['keyword_snippets']) for x in caps); rec['snippet_count']=sum(len(x['keyword_snippets']) for x in caps)
   rec['team_mentioned']=any(any(team.lower() in s['snippet'].lower() for s in x['keyword_snippets']) for x in caps)
   rec['plus15_mentions']=sum(sum(bool(re.search(r'\+?1[\.,]5',s['snippet'])) for s in x['keyword_snippets']) for x in caps)
   rec['team_total_mentions']=sum(sum(('team total' in s['snippet'].lower() or 'team goals' in s['snippet'].lower()) for s in x['keyword_snippets']) for x in caps)
   results.append(rec)
  b.close()
 res={'captured_at_local':datetime.now(TZ).isoformat(),'nav_errors':nav,'results':results,'guard':'Read-only sanitized network inspection. Query parameters/tokens removed; no bet clicks, wager, coupon, stake or account mutation.'}
 (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
 summ={'captured_at_local':res['captured_at_local'],'nav_errors':nav,'per_event':[{'rank':x['tierb_rank'],'event_id':x['event_id'],'team':x['selected_team'],'responses':len(x['responses']),'responses_with_keywords':x['responses_with_keyword_snippets'],'snippets':x['snippet_count'],'team_mentioned':x['team_mentioned'],'plus15_mentions':x['plus15_mentions'],'team_total_mentions':x['team_total_mentions'],'error':x.get('related_error')} for x in results]}
 (OUT/'summary.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summ,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
