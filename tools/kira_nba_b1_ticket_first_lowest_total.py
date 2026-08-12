from __future__ import annotations

import io
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT = Path("artifacts/kira_nba_b1_ticket_first_lowest_total")
OUT.mkdir(parents=True, exist_ok=True)
NBA_PARQUET = "https://raw.githubusercontent.com/llimllib/nba_data/main/data/gamelog_2026.parquet"
ODDS_URL = "https://www.kaggle.com/api/v1/datasets/download/zachht/wnba-odds-history"
UA = {"User-Agent": "Mozilla/5.0 KIRA-NBA-B1-TICKET-FIRST/1.0"}
MAIN_PREREG_BLOB = "71538443bd7d10e54ea9f6946ddabfe13f82c0c8"


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower().replace("la clippers", "los angeles clippers")).strip()


def pick(df, names):
    m = {str(c).upper(): str(c) for c in df.columns}
    for x in names:
        if x.upper() in m:
            return m[x.upper()]
    raise RuntimeError(f"missing {names}")


def nba_select(games: pd.DataFrame, target):
    # Exact frozen run_full6_r1 NBA B1 selector copied without threshold/ranking changes.
    target_ts = pd.Timestamp(target)
    prior = games[games.date < target_ts]
    today = games[games.date == target_ts]
    if today.empty:
        return [], []
    team_hist = defaultdict(list)
    opp_allowed = defaultdict(list)
    for _, r in prior.sort_values("date").iterrows():
        team_hist[r.home].append(int(r.home_pts)); team_hist[r.away].append(int(r.away_pts))
        opp_allowed[r.home].append(int(r.away_pts)); opp_allowed[r.away].append(int(r.home_pts))
    candidates = []
    for _, r in today.iterrows():
        for team, opp, pts in [(r.home, r.away, r.home_pts), (r.away, r.home, r.away_pts)]:
            h = team_hist.get(team, []); oh = opp_allowed.get(opp, [])
            if len(h) < 15 or len(oh) < 15:
                continue
            arr = np.asarray(h, dtype=float); oarr = np.asarray(oh, dtype=float)
            q10 = float(np.quantile(arr, 0.10, method="linear"))
            below = float(np.mean(arr < 90))
            last10 = float(np.mean(arr[-10:]))
            opp_hold = float(np.mean(oarr < 90))
            med = float(np.median(arr))
            if q10 < 92 or below > 0.05 or last10 < 105 or opp_hold > 0.10:
                continue
            candidates.append({"team": team, "opponent": opp, "q10": q10, "below90_rate": below,
                               "median": med, "last10_mean": last10, "opp_hold_below90_rate": opp_hold,
                               "points": int(pts), "pass": int(pts) >= 90})
    candidates.sort(key=lambda x: (-x["q10"], x["below90_rate"], -x["median"], -x["last10_mean"], x["team"]))
    return candidates[:2], candidates


def games():
    r = requests.get(NBA_PARQUET, headers=UA, timeout=180); r.raise_for_status()
    d = pd.read_parquet(io.BytesIO(r.content))
    cg = pick(d,["GAME_ID"]); cd=pick(d,["GAME_DATE"]); ct=pick(d,["TEAM_NAME"]); cp=pick(d,["PTS"]); cm=pick(d,["MATCHUP"])
    d=d[[cg,cd,ct,cp,cm]].copy(); d.columns=["game_id","game_date","team","pts","matchup"]
    d.game_id=d.game_id.astype(str).str.replace(r"\.0$","",regex=True).str.zfill(10)
    d=d[d.game_id.str.startswith("002")]; d.game_date=pd.to_datetime(d.game_date,errors="coerce"); d.pts=pd.to_numeric(d.pts,errors="coerce")
    d=d[d.game_date.notna() & d.pts.notna()]
    rows=[]
    for gid,g in d.groupby("game_id"):
        h=g[g.matchup.astype(str).str.contains("vs",case=False,regex=False)]; a=g[g.matchup.astype(str).str.contains("@",regex=False)]
        if len(h)!=1 or len(a)!=1: continue
        h=h.iloc[0]; a=a.iloc[0]
        rows.append({"date":pd.Timestamp(h.game_date).normalize(),"home":str(h.team),"away":str(a.team),"home_pts":int(h.pts),"away_pts":int(a.pts),"game_id":gid})
    return pd.DataFrame(rows).drop_duplicates("game_id").sort_values(["date","game_id"])


def odds():
    r=requests.get(ODDS_URL,headers=UA,timeout=240); r.raise_for_status()
    z=zipfile.ZipFile(io.BytesIO(r.content)); d=pd.read_csv(io.BytesIO(z.read("nba_detailed_odds.csv")))
    d["timestamp"]=pd.to_datetime(d.timestamp,errors="coerce"); d["Odds"]=pd.to_numeric(d.Odds,errors="coerce")
    d=d[d.Market.astype(str).str.fullmatch("Total – Game",case=False,na=False) & d.timestamp.notna() & d.Odds.notna()].copy()
    d["match_norm"]=d.matchup.map(norm); return d


def parse_over(s):
    m=re.match(r"^Over\s+([0-9]+(?:\.\d+)?)$",str(s).strip(),re.I)
    return float(m.group(1)) if m else None


def paired(g):
    rows=[]; start=max(g.date.min(),pd.Timestamp("2025-10-20")); end=min(g.date.max(),pd.Timestamp("2026-04-12"))
    for day in pd.date_range(start,end,freq="D"):
        _,u=nba_select(g[["date","home","away","home_pts","away_pts"]],day.date()); top=u[:4]
        by={(norm(x["team"]),norm(x["opponent"])):x for x in top}; seen=set()
        for rank,x in enumerate(top,1):
            key=tuple(sorted([norm(x["team"]),norm(x["opponent"])])); opp=by.get((norm(x["opponent"]),norm(x["team"])))
            if key in seen or not opp: continue
            ev=g[(g.date==day) & ((((g.home==x["team"])&(g.away==x["opponent"]))) | (((g.away==x["team"])&(g.home==x["opponent"]))))]
            if len(ev)!=1: continue
            e=ev.iloc[0]; seen.add(key)
            opp_rank=next(i for i,z in enumerate(top,1) if norm(z["team"])==norm(x["opponent"]) and norm(z["opponent"])==norm(x["team"]))
            rows.append({"date":day.date(),"team1":x["team"],"team2":x["opponent"],"rank1":rank,"rank2":opp_rank,"game_id":e.game_id,"actual_total":float(e.home_pts+e.away_pts),"matchup":f"{e.away} @ {e.home}"})
    return pd.DataFrame(rows),start,end


def strict_prior_snapshot(od,t1,t2,day):
    n1,n2=norm(t1),norm(t2)
    x=od[(od.timestamp>=pd.Timestamp(day)-pd.Timedelta(days=7)) & (od.timestamp<pd.Timestamp(day)) & od.match_norm.str.contains(re.escape(n1),regex=True) & od.match_norm.str.contains(re.escape(n2),regex=True)].copy()
    if x.empty: return x
    ts=x.timestamp.max(); x=x[x.timestamp==ts].copy(); x["line"]=x.Selection.map(parse_over); return x[x.line.notna()].copy()


def wilson_lower(w,n,z=1.959963984540054):
    if n<=0: return None
    p=w/n; den=1+z*z/n; center=p+z*z/(2*n); adj=z*((p*(1-p)/n+z*z/(4*n*n))**0.5)
    return (center-adj)/den


def main():
    g=games(); od=odds(); pairs,start,end=paired(g); rows=[]
    for _,r in pairs.iterrows():
        x=strict_prior_snapshot(od,r.team1,r.team2,r.date); rec=r.to_dict()
        if x.empty:
            rows.append(rec|{"market_status":"NO_STRICT_PRIOR_TOTAL"}); continue
        y=x.sort_values(["line","Odds"],ascending=[True,False]).iloc[0]
        margin=float(r.actual_total)-float(y.line); result="WIN" if margin>1e-9 else "LOSS" if margin<-1e-9 else "PUSH"
        rows.append(rec|{"market_status":"OK","total_line":float(y.line),"over_decimal":float(y.Odds),"snapshot":str(y.timestamp),"result":result})
    legs=pd.DataFrame(rows); valid=legs[legs.market_status=="OK"].copy()
    tickets=[]
    for day,x in valid.groupby("date"):
        bad=x[x.result=="LOSS"]
        tickets.append({"date":str(day),"legs":int(len(x)),"block_win":bool(bad.empty),"losses":int(len(bad))})
    t=pd.DataFrame(tickets); settled=int(((valid.result=="WIN")|(valid.result=="LOSS")).sum()) if len(valid) else 0
    bw=int(t.block_win.sum()) if len(t) else 0; bn=int(len(t))
    report={
      "experiment":"NBA-B1-TICKET-FIRST-LOWEST-STRICT-PRIOR-TOTAL-V1","status":"PREREGISTERED_TICKET_FIRST_MARKET_TRANSFER_DEV_ONLY",
      "main_prereg_blob":MAIN_PREREG_BLOB,"window":[str(start.date()),str(end.date())],
      "candidate_rule":"Both opponents independently qualify in frozen NBA B1 R1-R4 before market data; collapse to one full-game Total OVER candidate.",
      "market_rule":"Use latest archived Total-Game snapshot strictly before target calendar day, then lowest available OVER line; price not used to select contract.",
      "paired_candidates":int(len(pairs)),"market_valid":int(len(valid)),"wins":int((valid.result=="WIN").sum()) if len(valid) else 0,"losses":int((valid.result=="LOSS").sum()) if len(valid) else 0,"pushes":int((valid.result=="PUSH").sum()) if len(valid) else 0,
      "leg_win_rate_ex_push":float((valid.result=="WIN").sum()/settled) if settled else None,
      "block_days":bn,"block_days_won":bw,"block_day_win_rate":float(bw/bn) if bn else None,"block_wilson95_lcb":wilson_lower(bw,bn),
      "integrity":["Frozen B1 thresholds/ranking copied unchanged from run_full6_r1.","No price/line creates sports candidate.","Only odds timestamps strictly before target calendar day used.","DEV cannot self-promote; positive signal requires fresh independent/prospective validation plus exact Juancito current contract."],
    }
    pairs.to_csv(OUT/"paired_candidates.csv",index=False); legs.to_csv(OUT/"legs.csv",index=False); t.to_csv(OUT/"block_days.csv",index=False)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2,default=str),encoding="utf-8")
    print(json.dumps(report,indent=2,default=str))

if __name__=="__main__": main()
