from __future__ import annotations
import json,re,urllib.parse
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
START='https://deportes.juancitosport.com.do/BOSSWagering/Sportsbook/InternetBetTaker/?lng=es-ES&siteid=jssport'
OUT=Path('artifacts/kira_juancito_football_tierb_advanced_props_v14');TZ=ZoneInfo('America/Santo_Domingo')
TARGETS=[
 (2037,1961877,'CHINA','Shandong Luneng Taishan','AWAY',1),
 (2015,1962330,'POLAND','Ruch Chorzow','AWAY',2),
 (2059,1959023,'AUSTRIA','LASK Linz','AWAY',3),
]
def c(x):return re.sub(r'\s+',' ',str(x or '').replace('\xa0',' ')).strip()
def safe_url(u):
 try:
  z=urllib.parse.urlsplit(u); return urllib.parse.urlunsplit((z.scheme,z.netloc,z.path,'',''))
 except Exception:return ''
def main():
 OUT.mkdir(parents=True,exist_ok=True);nav=[];results=[]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':1800,'height':2200},locale='es-DO',timezone_id='America/Santo_Domingo')
  loaded=False
  for a in range(4):
   try:
    p.goto(START,wait_until='commit',timeout=45000);p.wait_for_timeout(10000)
    if p.locator('#tblSH_53').count():loaded=True;break
   except Exception as ex:nav.append(f'{a+1}:{type(ex).__name__}:{ex}')
  if not loaded:b.close();raise RuntimeError('BOSS unavailable: '+' | '.join(nav))
  for h,e,country,team,side,rank in TARGETS:
   rec={'header_id':h,'event_id':e,'country':country,'selected_team':team,'selected_side':side,'tierb_rank':rank}
   try:p.evaluate("([h,e])=>RelatedEvents(h,e,1,0)",[h,e]);p.wait_for_timeout(5000)
   except Exception as ex:rec['related_error']=f'{type(ex).__name__}:{ex}';results.append(rec);continue
   try:
    iframe=p.locator('#iframeDSTProps'); rec['iframe_present']=iframe.count()>0
    if not rec['iframe_present']:results.append(rec);continue
    src=iframe.get_attribute('src') or ''
    rec['iframe_host_path']=safe_url(src)
    # Never persist token/query.
    frame=None
    for _ in range(20):
     for fr in p.frames:
      if 'digitalsportstech.com' in fr.url and f'event={e}' in fr.url: frame=fr;break
     if frame:break
     p.wait_for_timeout(500)
    if not frame:
     rec['frame_loaded']=False;results.append(rec);continue
    rec['frame_loaded']=True
    try:frame.wait_for_load_state('domcontentloaded',timeout=20000)
    except Exception:pass
    p.wait_for_timeout(10000)
    try:text=c(frame.locator('body').inner_text(timeout=15000))
    except Exception as ex:text='';rec['frame_text_error']=f'{type(ex).__name__}:{ex}'
    rec['frame_text']=text[:60000]
    low=text.lower(); rec['selected_team_mentioned']=team.lower() in low
    rec['plus15_literal']=('+1.5' in text or '+1½' in text or ' +1.5 ' in text)
    rec['team_total_literal']=('team total' in low or 'total por equipo' in low or 'team goals' in low)
    rec['double_chance_literal']=('double chance' in low or 'doble oportunidad' in low)
    rec['draw_no_bet_literal']=('draw no bet' in low or 'empate no' in low)
    # Collect visible text chunks only; no URLs/tokens.
    try:
     els=frame.locator('button,[role=button],label,option,li,td,span,div').evaluate_all("""els=>els.map(x=>({tag:x.tagName,cls:typeof x.className==='string'?x.className:'',text:(x.innerText||x.textContent||'').replace(/\\s+/g,' ').trim()})).filter(x=>x.text&&x.text.length<=500)""")
    except Exception:els=[]
    # retain only market-relevant chunks, deduped
    keep=[];seen=set()
    for x in els:
     t=c(x.get('text'))
     if not t or t in seen:continue
     if any(k in t.lower() for k in [team.lower(),'handicap','spread','team total','team goals','total','double chance','draw no bet','+1.5','1.5']):
      seen.add(t);keep.append({'tag':x['tag'],'cls':c(x.get('cls')),'text':t})
     if len(keep)>=250:break
    rec['relevant_visible_chunks']=keep
   except Exception as ex:rec['iframe_error']=f'{type(ex).__name__}:{ex}'
   results.append(rec)
  b.close()
 res={'captured_at_local':datetime.now(TZ).isoformat(),'nav_errors':nav,'results':results,'guard':'Read-only cross-origin rendered iframe inspection. Query tokens/URLs are stripped; no click, wager, coupon, account or stake mutation.'}
 (OUT/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
 summ={'captured_at_local':res['captured_at_local'],'nav_errors':nav,'per_event':[{'rank':x['tierb_rank'],'event_id':x['event_id'],'team':x['selected_team'],'iframe_present':x.get('iframe_present'), 'frame_loaded':x.get('frame_loaded'),'selected_team_mentioned':x.get('selected_team_mentioned'),'plus15_literal':x.get('plus15_literal'),'team_total_literal':x.get('team_total_literal'),'double_chance_literal':x.get('double_chance_literal'),'draw_no_bet_literal':x.get('draw_no_bet_literal'),'relevant_chunks':len(x.get('relevant_visible_chunks',[])),'error':x.get('iframe_error') or x.get('related_error')} for x in results]}
 (OUT/'summary.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summ,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
