"""Event-conditioned path simulation and ambiguity-aware payoffs. No calibrated market probabilities."""
import json,hashlib,os,itertools
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from analyze_portfolio import ROOT,serial

date=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
base=ROOT/f"data/ideal_review/{date}"
a=json.loads((base/"analysis.json").read_text())
intel=json.loads((base/"intelligence.json").read_text())
cfg=json.loads((ROOT/"research/daily_config.json").read_text())
codes=[p["code"] for p in a["policy"]["positions"]]
factors=["510300","515880","510880","006075","002611"]
levels={c:pd.read_csv(base/"nav"/f"{c}.csv",parse_dates=["date"]).set_index("date").wealth for c in set(codes+factors)}
joined=pd.DataFrame(levels).dropna()
# Restrict the common MC estimation sample to the youngest independently managed strategy.
logret=np.log(joined/joined.shift(1)).dropna().loc["2026-05-30":].tail(120)
assert len(logret)>=50
X=logret[factors].to_numpy();Y=logret[codes].to_numpy()
n=len(X);horizon=cfg["horizon_days"];nsim=cfg["simulations_per_branch"]
rng=np.random.default_rng(cfg["seed"])
selectors={}
for c in codes:
    selectors[c]=[3,0] if c=="027170" else ([3] if c=="006075" else ([4] if c=="002611" else [0,1,2]))

def fit(index):
    B=np.zeros((len(codes),5));intercept=np.zeros(len(codes))
    for i,c in enumerate(codes):
        if c in ["006075","002611"]:
            B[i,3 if c=="006075" else 4]=1;continue
        selected=selectors[c]
        design=np.column_stack([np.ones(len(index)),X[index][:,selected]])
        coef=np.linalg.lstsq(design,Y[index,i],rcond=None)[0]
        intercept[i]=coef[0];B[i,selected]=coef[1:]
    return B,intercept

B,intercept=fit(np.arange(n))
residual=Y-X@B.T-intercept
residual-=residual.mean(axis=0)
noise=np.column_stack([X-X.mean(axis=0),residual])

def blocks(length,reps):
    start=rng.integers(0,n-4,size=(reps,int(np.ceil(length/5))))
    return (start[:,:,None]+np.arange(5)).reshape(reps,-1)[:,:length]

# Coefficient uncertainty is common across branches/plans, preserving paired comparisons.
fit_indexes=blocks(n,300)
draws=np.array([fit(i)[0] for i in fit_indexes])
draws=draws[np.arange(nsim)%len(draws)]
innovations=noise[blocks(horizon,nsim)]
cashflow_alerts=[i for i in intel["items"] if i.get("metrics",{}).get("operating_cashflow_ytd_cny",0)<0]
uncertainty_multiplier=cfg.get("cashflow_watch_uncertainty_multiplier",1.15) if cashflow_alerts else 1.
future_days=pd.bdate_range(pd.Timestamp(date)+pd.Timedelta(days=1),periods=horizon)
event_indexes=sorted(set(min(horizon-1,max(0,int(future_days.searchsorted(pd.Timestamp(e["date"])))))
                         for e in intel["events"] if e["verified"] and pd.Timestamp(e["date"])<=future_days[-1]))
timing=np.ones(horizon)/horizon
if event_indexes:
    timing*=1-cfg["event_impulse_fraction"]
    for i in event_indexes:timing[i]+=cfg["event_impulse_fraction"]/len(event_indexes)
assert np.isclose(timing.sum(),1)
plans={r["id"]:np.array([r["amounts"].get(c,0)/a["policy"]["total_cny"] for c in codes])
       for r in a["weekly"]["results"] if r["id"]!="old_reported_scaled"}
bounds=cfg["branch_weight_bounds"].copy()
weight_rule="固定人工权重范围；不由价格趋势或新闻情绪生成概率。"
if intel["rates"] and intel["rates"]["change20_bp"]>=25:
    bounds={**bounds,"bull":[.10,.35],"rates":[.15,.40]}
    weight_rule="官方实际利率20个公布点上升至少25bp：压力分支人工下限提高到15%，修复上限收至35%；阈值未校准。"
scenario_order=[s["id"] for s in a["policy"]["scenarios"]]

def vertices():
    result=[]
    # Extremes of simplex with interval constraints: at most one coordinate not at a bound.
    for free in range(len(scenario_order)):
        rest=[i for i in range(len(scenario_order)) if i!=free]
        for combination in itertools.product([0,1],repeat=len(rest)):
            p=np.zeros(len(scenario_order))
            for i,side in zip(rest,combination):p[i]=bounds[scenario_order[i]][side]
            p[free]=1-p.sum()
            if bounds[scenario_order[free]][0]-1e-9<=p[free]<=bounds[scenario_order[free]][1]+1e-9:result.append(p)
    return np.unique(np.round(result,10),axis=0)

v=vertices();assert len(v) and np.allclose(v.sum(axis=1),1)
branches=[];terminal_by_plan={k:[] for k in plans}
path_fans={}
for s in a["policy"]["scenarios"]:
    scenario_shock=np.log1p([s[k] for k in ["market","communication","dividend","sp500","gold"]])
    # 50% innovation scale around expert shock; full residual scale, both broadened in pressure branch.
    multiplier=cfg["tail_noise_multiplier"] if s["id"] in ["bear","rates"] else 1.
    factor_noise=innovations[:,:,:5].copy()
    if s["id"] in ["bull","bear"]:factor_noise[:,:,1]*=uncertainty_multiplier
    factor_paths=timing[None,:,None]*scenario_shock[None,None,:]+factor_noise*.5*multiplier
    log_fund=np.einsum("sdf,skf->sdk",factor_paths,draws)+innovations[:,:,5:]*multiplier
    assert np.isfinite(log_fund).all()
    fund_returns=np.expm1(log_fund)
    responses={}
    for name,w in plans.items():
        daily=fund_returns@w
        wealth=np.cumprod(1+daily,axis=1)
        terminal=wealth[:,-1]-1
        full=np.column_stack([np.ones(nsim),wealth]);dd=(full/np.maximum.accumulate(full,axis=1)-1).min(axis=1)
        loss5=terminal<=-.05
        q=np.quantile(terminal,[.05,.10,.5,.9,.95])
        responses[name]={"mean":terminal.mean(),"median":q[2],"q05":q[0],"q10":q[1],"q90":q[3],"q95":q[4],
                         "positive_path_fraction":(terminal>0).mean(),"loss5_path_fraction":loss5.mean(),
                         "expected_shortfall10":terminal[terminal<=q[1]].mean(),
                         "path_drawdown_q10":np.quantile(dd,.1)}
        terminal_by_plan[name].append(terminal)
        if name=="target":path_fans[s["id"]]={"p10":np.quantile(wealth,.1,axis=0)-1,
                                             "median":np.median(wealth,axis=0)-1,
                                             "p90":np.quantile(wealth,.9,axis=0)-1}
    fund_terminal=np.prod(1+fund_returns,axis=1)-1
    branches.append({"id":s["id"],"name":s["name"],"weight_bounds":bounds[s["id"]],"responses":responses,
                     "fund_responses":{c:{"mean":fund_terminal[:,i].mean(),"q10":np.quantile(fund_terminal[:,i],.1),"q90":np.quantile(fund_terminal[:,i],.9)} for i,c in enumerate(codes)},
                     "shock":{k:s[k] for k in ["market","communication","dividend","sp500","gold"]}})
robust=[]
for name in plans:
    bybranch=np.array(terminal_by_plan[name])
    means=bybranch.mean(axis=1)
    pos=np.maximum(bybranch,0).mean(axis=1)
    neg=np.maximum(-bybranch,0).mean(axis=1)
    gains=v@pos;losses=v@neg;expected=v@means
    loss5=v@(bybranch<-.05).mean(axis=1)
    positive=v@(bybranch>0).mean(axis=1)
    ratio=gains/np.maximum(losses,1e-10)
    robust.append({"id":name,"mean_range":[expected.min(),expected.max()],
                   "gain_loss_ratio_range":[ratio.min(),ratio.max()],
                   "positive_fraction_range":[positive.min(),positive.max()],
                   "loss5_fraction_range":[loss5.min(),loss5.max()],
                   "minimum_mean_weights":dict(zip(scenario_order,v[expected.argmin()])),
                   "maximum_mean_weights":dict(zip(scenario_order,v[expected.argmax()]))})
target_means=np.array([b["responses"]["target"]["mean"] for b in branches])
up=target_means[scenario_order.index("bull")];down=target_means[scenario_order.index("bear")]
breakeven=-down/(up-down) if up>0>down else None
# Data-shock calibration of residual risk only: honest walk-forward, no hypothetical event labels.
backtest=[]
for i in range(60,len(logret)-horizon+1,horizon):
    history=Y[:i]@plans["target"]
    actual=np.expm1(Y[i:i+horizon]@plans["target"]).copy()
    realized=np.prod(1+actual)-1
    sd=np.std(history,ddof=1)*np.sqrt(horizon)
    backtest.append({"origin":str(logret.index[i-1].date()),"end":str(logret.index[i+horizon-1].date()),
                     "realized":realized,"zero_drift_gaussian90":[-1.645*sd,1.645*sd]})
public=Path(os.environ.get("RESEARCH_PUBLIC_ROOT",ROOT/"publish/github-pages"))
prospective=[]
for old_file in sorted((public/"reports").glob("*/forward.json")):
    if old_file.parent.name>=date:continue
    old_model=json.loads(old_file.read_text())
    old_analysis=json.loads((old_file.parent/"analysis.json").read_text())
    old_positions=old_analysis["policy"]["positions"]
    if any(p["code"] not in joined for p in old_positions):continue
    after=joined.loc[joined.index>pd.Timestamp(old_model["date"])]
    span=old_model["horizon_sessions"]
    record={"origin_report":old_model["date"],"status":"pending","available_common_intervals":max(0,len(after)-1)}
    if len(after)>span:
        old_weights=np.array([p["amount_cny"]/old_analysis["policy"]["total_cny"] for p in old_positions])
        old_codes=[p["code"] for p in old_positions]
        realized=float((after.iloc[span][old_codes]/after.iloc[0][old_codes]-1)@old_weights)
        record.update(status="matured",entry=str(after.index[0].date()),end=str(after.index[span].date()),realized=realized,
                      note="研究发布后第一个共同净值买入代理、期内不交易；不同于模型每日再平衡，分支事实仍需核验。")
    prospective.append(record)
result={"date":date,"horizon_sessions":horizon,"approximate_end":str(future_days[-1].date()),
        "calendar_note":"路径用20个工作日近似；节假日和场外成交时差另有误差。",
        "estimation":{"start":str(logret.index[0].date()),"end":str(logret.index[-1].date()),"n":n,
                      "coefficients":dict(zip(codes,B.tolist())),"factor_codes":factors},
        "simulations_per_branch":nsim,"branches":branches,"robust":robust,"weight_rule":weight_rule,
        "vertices":v,"breakeven_bull_vs_bear":breakeven,
        "breakeven_note":"只在修复/增长担忧两情景且忽略其他分支时，盈亏平衡所需修复权重；不是估计出的实际上涨概率。",
        "event_indexes":event_indexes,"events":intel["events"],"path_fans":path_fans,
        "evidence_adjustments":{"earnings_uncertainty_multiplier":uncertainty_multiplier,
                                "cashflow_alert_sources":[i["url"] for i in cashflow_alerts],
                                "note":"监测公司现金流为负时，将盈利相关分支的通信扰动扩大15%；这是保守敏感性规则，不以单公司替代行业结论，也不改变上涨概率。"},
        "path_days":[str(x.date()) for x in future_days],
        "calibration":{"status":"uncalibrated_event_probabilities","completed_walkforward_nodes":len(backtest),"nodes":backtest,"prospective":prospective,
                       "note":"这里只能审视短样本残差尺度；事件分支没有足够历史标签与前瞻实绩，不输出可信市场胜率。每日冻结后再登记已实现的20日表现。"},
        "limits":["分支冲击和权重界限为人工假设；日历事件改变路径冲击时点，不制造预期收益。",
                  "共同5日块扰动保留残差共振，300组参数重采样；不把模拟分位数当真实未来置信区间。",
                  "冲击附近加入半倍因子噪声、压力分支残差放大1.35；这些尺度是保守研究设定而非样本外最优。",
                  "盈亏比=权重下正收益期望/负收益绝对值期望；只有假设集内的含义。",
                  "路径每日再平衡，未含申赎费、在途、实际持仓变化；目标配置未记为交易。"],
        "inputs":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                  [base/"analysis.json",base/"intelligence.json",ROOT/"research/daily_config.json",Path(__file__)]}}
(base/"forward.json").write_text(json.dumps(serial(result),ensure_ascii=False,indent=2,allow_nan=False))
np.savez_compressed(base/"forward_paths.npz",**{k:np.array(value) for k,value in terminal_by_plan.items()})
print(json.dumps(serial({"robust":robust,"breakeven":breakeven,"events":intel["events"],"n":n}),ensure_ascii=False,indent=2))
