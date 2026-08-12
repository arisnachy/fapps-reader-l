from __future__ import annotations
import json,re,urllib.parse
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_dst_protocol_v17');TZ=ZoneInfo('America/Santo_Domingo')
H,E=2037,1961877

def safe_url(u):
 try:
  z=urllib.parse.urlsplit(u);return urllib.parse.urlunsplit((z.scheme,z.netloc,z.path,'',''))
 except:return ''
def redact(s):
 s=re.sub(r'(?i)(token|authorization|jwt|session|cookie)["\'\s:=]+[A-Za-z0-9._~+/=-]{8,}',r'\1=[REDACTED]',s)
 s=re.sub(r'\b[A-Za-z0-9_-]{36,}\b','[REDACTED_LONG_TOKEN]',s)
 return re.sub(r'\s+',' ',s).strip()
def main():
 OUT.mkdir(parents=True,exist_ok=True);nav=[];result={'event_id':E}
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);ctx=b.new_context(locale='es-DO',timezone_id='America/Santo_Domingo');p=ctx.new_page();loaded=False
  for a in range(4):
   try:
    p.goto(START,wait_until='commit',timeout=45000);p.wait_for_timeout(10000)
    if p.locator('#tblSH_53').count():loaded=True;break
   except Exception as ex:nav.append(f'{a+1}:{type(ex).__name__}:{ex}')
  if not loaded:b.close();raise RuntimeError('BOSS unavailable: '+' | '.join(nav))
  caps=[]
  def onr(r):
   if 'digitalsportstech' not in r.url.lower():return
   rec={'url_path':safe_url(r.url),'status':r.status,'content_type':r.headers.get('content-type','')}
   try:body=r.text()
   except Exception:body=''
   if '/api/' in r.url.lower(): rec['body_excerpt']=redact(body[:12000])
   if re.search(r'/main-[A-Z0-9]+\.js$',safe_url(r.url),re.I):
    paths=sorted(set(re.findall(r'["\'](/api/[A-Za-z0-9_./{}?=&:-]{2,180})["\']',body)))
    # also capture literal API-ish strings without leading slash
    paths+=sorted(set('/api/'+x for x in re.findall(r'["\']api/([A-Za-z0-9_./{}?=&:-]{2,180})["\']',body)))
    rec['api_path_literals']=sorted(set(paths))[:500]
    terms=[]
    for pat in [r'security/challenge',r'application-config',r'event',r'market',r'fixture',r'offer',r'proposition',r'bet-builder']:
     for m in re.finditer(pat,body,re.I):
      terms.append({'term':pat,'snippet':redact(body[max(0,m.start()-450):min(len(body),m.end()+850)])[:1800]})
      if len(terms)>=120:break
     if len(terms)>=120:break
    rec['protocol_snippets']=terms
   caps.append(rec)
  p.on('response',onr)
  p.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[H,E]);p.wait_for_timeout(25000)
  try:p.remove_listener('response',onr)
  except:pass
  result.update({'captured_at_local':datetime.now(TZ).isoformat(),'nav_errors':nav,'responses':caps,'safe_paths':sorted(set(x['url_path'] for x in caps)),'api_responses':[x for x in caps if '/api/' in x['url_path']],'main_script_records':[x for x in caps if x.get('api_path_literals') is not None],'guard':'Read-only protocol introspection. No token/query persisted, no challenge bypass, no bet/coupon/account/stake mutation.'})
  b.close()
 (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 summ={'captured_at_local':result['captured_at_local'],'event_id':E,'safe_paths':result['safe_paths'],'api_response_count':len(result['api_responses']),'main_script_count':len(result['main_script_records']),'api_path_literals':sorted(set(y for x in result['main_script_records'] for y in x.get('api_path_literals',[])))[:300]}
 (OUT/'summary.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summ,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
