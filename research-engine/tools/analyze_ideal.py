"""Evaluate the screenshot allocation with dated NAVs and conditional, non-probabilistic scenarios."""
import json,hashlib,os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import statsmodels.api as sm
from analyze_portfolio import ROOT,serial,block_indices

date=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
base=ROOT/f"data/ideal_review/{date}"
if (Path(os.environ.get("RESEARCH_PUBLIC_ROOT",ROOT/"publish/github-pages"))/f"reports/{date}/manifest.json").exists():
    raise SystemExit("Published date: do not overwrite its analysis.")
policy_path=ROOT/f"research/ideal_policy_{date}.json"
policy=json.loads(policy_path.read_text())
manifest=json.loads((base/"nav/manifest.json").read_text())
assert all(x["status"]=="collected" for x in manifest)
levels={p.stem:pd.read_csv(p,parse_dates=["date"]).set_index("date").wealth for p in (base/"nav").glob("*.csv")}
amounts={p["code"]:p["amount_cny"] for p in policy["positions"]}
total=sum(amounts.values());assert total==policy["total_cny"]
dates=pd.date_range("2021-01-01",pd.Timestamp(date)-pd.Timedelta(days=1),freq="W-FRI")
weekly={}
for c,s in levels.items():
    weekly[c]=[s.loc[:d].iloc[-1] if len(s.loc[:d]) and (d-s.loc[:d].index[-1]).days<=7 else np.nan for d in dates]
wl=pd.DataFrame(weekly,index=dates)
wr=wl.pct_change(fill_method=None)
target_codes=list(amounts)
common=wr[target_codes].dropna().tail(52)
weights=np.array(list(amounts.values()))/total
plans={"target":amounts.copy()}
no_gold={c:v*total/(total-amounts["002611"]) for c,v in amounts.items() if c!="002611"}
plans["no_gold"]=no_gold
for fraction in [.06,.20]:
    plans[f"gold_{fraction:.0%}"]={c:v*total*(1-fraction)/(total-amounts["002611"]) for c,v in amounts.items() if c!="002611"}
    plans[f"gold_{fraction:.0%}"]["002611"]=fraction*total
eight=amounts.copy()
eight["021902"]+=eight.pop("519697")
eight["006075"]+=eight.pop("027170")
plans["eight_role_merge"]=eight
old=json.loads((ROOT/"data/positions_2026-09-17.json").read_text())
old_amounts={p["code"]:p["amount_cny"] for p in old["positions"] if p["status"]!="pending_cancellable"}
plans["old_reported_scaled"]={c:v*total/sum(old_amounts.values()) for c,v in old_amounts.items()}
all_codes=list(dict.fromkeys(c for p in plans.values() for c in p))
sample=wr[all_codes].reindex(common.index)
assert sample.notna().all().all()

def metrics(r,annual=52):
    r=np.asarray(r);path=np.r_[1,np.cumprod(1+r)]
    return {"n":len(r),"return":path[-1]-1,"vol":np.std(r,ddof=1)*np.sqrt(annual),
            "mdd":np.min(path/np.maximum.accumulate(path)-1),"worst":np.min(r)}
def plan_return(frame,a):
    return sum(frame[c]*v/total for c,v in a.items())
target=plan_return(sample,amounts)
indices=block_indices(len(sample),2000,4,np.random.default_rng(20261019))
comparisons=[]
paths={}
for name,a in plans.items():
    assert np.isclose(sum(a.values()),total)
    r=plan_return(sample,a)
    delta=(r.to_numpy()[indices].std(axis=1,ddof=1)-target.to_numpy()[indices].std(axis=1,ddof=1))*np.sqrt(52)
    comparisons.append({"id":name,"amounts":a,**metrics(r),"vol_delta_vs_target_ci90":np.quantile(delta,[.05,.95])})
    paths[name]=np.r_[1,np.cumprod(1+r)]
cov=common.cov().to_numpy();variance=weights@cov@weights
contributions=weights*(cov@weights)/variance
paircorr=common.corr()
interactions=[{"a":a,"b":b,"n":len(common),"correlation":paircorr.loc[a,b]}
              for a,b in [("010390","011370"),("006075","027170"),("519697","022714"),("519697","021902"),("002611","006075"),("002611","011370"),("022415","021902")]]
# Gold diversification across windows, with mainland technology as a common-date comparator.
tech=wr[["515880","512480","512720"]].mean(axis=1,skipna=False)
gold_evidence=[]
for n in [26,52,104]:
    f=pd.concat([tech.rename("tech"),wr["002611"].rename("gold"),wr["510300"].rename("market")],axis=1).tail(n).dropna()
    down=f.tech<0;crash=f.tech<=-.03;both=(f.tech<0)&(f.gold<0)
    gold_evidence.append({"window":n,"n":len(f),"correlation_tech":f.gold.corr(f.tech),"correlation_market":f.gold.corr(f.market),
        "technology_down_weeks":int(down.sum()),"gold_positive_when_tech_down":float((f.loc[down,"gold"]>0).mean()),
        "gold_mean_when_tech_down":f.loc[down,"gold"].mean(),"both_down_weeks":int(both.sum()),
        "tech_crash_weeks":int(crash.sum()),"gold_mean_when_tech_crash":f.loc[crash,"gold"].mean(),
        "gold_weekly_vol":f.gold.std()*np.sqrt(52)})
overseas=[]
for n in [26,52,104]:
    f=wr[["006075","027170"]].tail(n).dropna()
    if len(f)>2:overseas.append({"requested_window":n,"actual_n":len(f),"correlation":f.corr().iloc[0,1]})
# Same product A sensitivity restricted to the current global fund team.
sens=wr.copy();sens["027170"]=sens["519696"]
sens=sens.loc[sens.index-pd.Timedelta(days=7)>=pd.Timestamp("2026-01-22"),target_codes].dropna()
sensitivity={"basis":"仅交银环球以同产品A替代，从2026-01-22新团队以后；其他份额不拼接。",
             "start":str((sens.index[0]-pd.Timedelta(days=7)).date()),"end":str(sens.index[-1].date()),**metrics(plan_return(sens,amounts))}
gold_alt=sample.copy();gold_alt["002611"]=wr["000217"].reindex(sample.index)
gold_proxy_check={"proxy":"华安黄金ETF联接C000217",**metrics(plan_return(gold_alt,amounts)),
                  "weekly_correlation":wr[["002611","000217"]].tail(104).dropna().corr().iloc[0,1]}
daily_levels=pd.DataFrame({c:levels[c] for c in target_codes}).dropna()
dr=daily_levels.pct_change(fill_method=None).dropna()
daily_r=dr@weights
daily_result={"start":str(daily_levels.index[0].date()),"end":str(daily_levels.index[-1].date()),
              **metrics(daily_r,252),"note":"共同正式估值日、每日恢复权重，显示周内峰谷敏感性；不同于每周恢复权重。"}
bh_levels=(1+common).cumprod()@weights
bh_r=bh_levels/np.r_[1,bh_levels.to_numpy()[:-1]]-1
buyhold=metrics(bh_r)
# Quarter-like fixed historical intervals based on the actually available daily level endpoints.
events=[]
for label,start,end in [("七月","2026-06-30","2026-07-31"),("八月","2026-07-31","2026-08-31"),("九月","2026-08-31","2026-09-30"),("十月已公布","2026-09-30",str(daily_levels.index[-1].date()))]:
    s=daily_levels.loc[:start].index[-1];e=daily_levels.loc[:end].index[-1]
    changes=daily_levels.loc[e]/daily_levels.loc[s]-1
    events.append({"name":label,"start":str(s.date()),"end":str(e.date()),
                   "return":changes@weights,"gold_contribution":changes["002611"]*amounts["002611"]/total,
                   "method":"区间起点按目标金额权重，期内不再平衡；是今日目标的事后回放，不是用户实盘。"})
# No intercept projection; fit only actual, common-date NAV returns.
fits={}
for c in target_codes:
    if c in ["006075","002611"]:continue
    refs=["006075","510300"] if c=="027170" else ["510300","515880","510880"]
    frame=pd.concat([levels[x].rename(x) for x in [c]+refs],axis=1).dropna().pct_change(fill_method=None).dropna()
    windows={}
    for window in [60,120,252]:
        f=frame.tail(window)
        if c=="010390":f=f.loc["2026-05-29":] # independent phase only
        if c=="011370":f=f.loc["2025-03-05":]
        if c=="027170":f=f.loc["2026-01-23":]
        x=pd.DataFrame({"sp500":f["006075"],"market":f["510300"]}) if c=="027170" else pd.DataFrame(
            {"market":f["510300"],"technology_excess":f["515880"]-f["510300"],"value_excess":f["510880"]-f["510300"]})
        model=sm.OLS(f[c],sm.add_constant(x)).fit(cov_type="HAC",cov_kwds={"maxlags":5})
        windows[str(window)]={"n":len(f),"start":str(f.index[0].date()),"end":str(f.index[-1].date()),
            "coef":model.params.to_dict(),"r2":model.rsquared,"residual_daily_std":model.resid.std(ddof=1),
            "ci90":{k:row.tolist() for k,row in model.conf_int(alpha=.1).iterrows()}}
    fits[c]=windows
scenarios=[]
for sc in policy["scenarios"]:
    fund_responses={};sum_responses={}
    for window in ["60","120","252"]:
        fund_responses[window]={}
        for c in target_codes:
            if c=="006075":value=sc["sp500"]
            elif c=="002611":value=sc["gold"]
            else:
                beta=fits[c][window]["coef"]
                value=(beta["sp500"]*sc["sp500"]+beta["market"]*sc["market"]) if c=="027170" else (
                    beta["market"]*sc["market"]+beta["technology_excess"]*(sc["communication"]-sc["market"])+beta["value_excess"]*(sc["dividend"]-sc["market"]))
            fund_responses[window][c]=value
        for name,a in plans.items():
            if name=="old_reported_scaled":continue
            sum_responses.setdefault(name,{})[window]=sum(fund_responses[window][c]*v/total for c,v in a.items())
    scenarios.append({**sc,"fund_responses":fund_responses,"plans":{k:{"by_window":v,"min":min(v.values()),"max":max(v.values()),
        "min_cny":min(v.values())*total,"max_cny":max(v.values())*total} for k,v in sum_responses.items()}})
snapshot=[]
for c in target_codes+["000217","510300","515880","510880"]:
    s=levels[c]
    snapshot.append({"code":c,"date":str(s.index[-1].date()),"return1":s.iloc[-1]/s.iloc[-2]-1,"return5":s.iloc[-1]/s.iloc[-6]-1,
        "return20":s.iloc[-1]/s.iloc[-21]-1,"return60":s.iloc[-1]/s.iloc[-61]-1,
        "drawdown120":s.iloc[-1]/s.tail(121).max()-1})
latest_event_codes=[c for c in target_codes if c not in ["006075","027170"]]
latest_event_levels=pd.DataFrame({c:levels[c] for c in latest_event_codes}).dropna()
event_start,event_end=latest_event_levels.index[-2:]
latest_event_codes=[c for c in target_codes if event_start in levels[c].index and event_end in levels[c].index]
event_returns=pd.Series({c:levels[c].loc[event_end]/levels[c].loc[event_start]-1 for c in latest_event_codes})
covered_amount=sum(amounts[c] for c in latest_event_codes)
latest_event={"start":str(event_start.date()),"end":str(event_end.date()),
              "fund_returns":event_returns.to_dict(),"covered_cny":covered_amount,"coverage":covered_amount/total,
              "change_cny":sum(event_returns[c]*amounts[c] for c in latest_event_codes),
              "covered_return":sum(event_returns[c]*amounts[c] for c in latest_event_codes)/covered_amount,
              "whole_portfolio_return":float(sum(event_returns[c]*amounts[c] for c in latest_event_codes)/total) if len(latest_event_codes)==len(target_codes) else None,
              "missing_codes":[c for c in target_codes if c not in latest_event_codes],
              "note":"目标金额的境内及黄金部分静态映射，未披露同日QDII不填0，不是账户盈亏。"}
previous=None
if policy.get("previous_review_date"):
    prev_path=ROOT/f"data/ideal_review/{policy['previous_review_date']}/analysis.json"
    prev=json.loads(prev_path.read_text())
    prev_rows={r["code"]:r for r in prev["latest"]}
    feedback=[]
    for c in target_codes:
        anchor=prev_rows[c]["date"]
        feedback.append({"code":c,"from":anchor,"to":str(levels[c].index[-1].date()),
                         "return":levels[c].iloc[-1]/levels[c].loc[anchor]-1})
    frozen=daily_levels.loc[prev["date"]:]
    previous={"date":prev["date"],"file":str(prev_path.relative_to(ROOT)),"fund_updates":feedback,
              "followup":None,"note":"逐只净值更新可能覆盖研究日前行情，不能视为建议发表后的预测成绩。"}
    if len(frozen)>=2:
        previous["followup"]={"start":str(frozen.index[0].date()),"end":str(frozen.index[-1].date()),
                              "return":float((frozen.iloc[-1]/frozen.iloc[0]-1)@weights)}
groups={
    "domestic_technology":sum(amounts[c] for c in ["022714","021180","010390","011370"])/total,
    "domestic_value":sum(amounts[c] for c in ["022415","021902"])/total,
    "domestic_flexible":amounts["519697"]/total,"overseas":(amounts["006075"]+amounts["027170"])/total,
    "gold":amounts["002611"]/total}
result={"date":date,"policy":policy,"groups":groups,"latest":snapshot,"latest_event":latest_event,"previous_review":previous,
        "weekly":{"cutoff":str(dates[-1].date()),"start":str((sample.index[0]-pd.Timedelta(days=7)).date()),"n":len(sample),
                  "results":comparisons,"risk_contributions":dict(zip(target_codes,contributions)),
                  "paths":{"dates":[str((sample.index[0]-pd.Timedelta(days=7)).date())]+[str(d.date()) for d in sample.index],"values":paths}},
        "daily":daily_result,"buyhold":buyhold,"a_sensitivity":sensitivity,"gold_proxy_sensitivity":gold_proxy_check,
        "interactions":interactions,"gold_evidence":gold_evidence,"overseas_evidence":overseas,
        "events":events,"fits":fits,"scenarios":scenarios,
        "inputs":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                  [policy_path,base/"nav/manifest.json",ROOT/"data/positions_2026-09-17.json",ROOT/"tools/analyze_ideal.py"]
                  +([prev_path] if previous else [])},
        "nav_hashes":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (base/"nav").glob("*.csv")}}
(base/"analysis.json").write_text(json.dumps(serial(result),ensure_ascii=False,indent=2,allow_nan=False))
print(json.dumps(serial({k:v for k,v in result.items() if k not in ["fits","inputs","policy"]}),ensure_ascii=False,indent=2))
