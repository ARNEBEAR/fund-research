"""Versioned multi-window portfolio diagnostics; no account or forecast claims."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT/path).read_text())


def serial(value):
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [serial(v) for v in value]
    if isinstance(value,np.ndarray):return serial(value.tolist())
    if isinstance(value,(np.integer,)):return int(value)
    if isinstance(value,(np.floating,)):return float(value) if np.isfinite(value) else None
    if isinstance(value,float) and not np.isfinite(value):return None
    return value


def wcov(frame):
    age=(frame.index[-1]-frame.index).days.to_numpy()/7
    return np.cov(frame.to_numpy(),rowvar=False,aweights=2**(-age/13))


def corr(frame):
    if len(frame)<3 or (frame.std()<1e-10).any():return None
    c=wcov(frame)
    return float(c[0,1]/np.sqrt(c[0,0]*c[1,1]))


def block_indices(n,replicates,block,rng):
    starts=rng.integers(0,n-block+1,size=(replicates,int(np.ceil(n/block))))
    return (starts[:,:,None]+np.arange(block)).reshape(replicates,-1)[:,:n]


def portfolio_metrics(frame,amounts):
    weights=np.array([amounts.get(c,0) for c in frame.columns],float)
    weights/=weights.sum()
    r=frame.to_numpy()@weights
    path=np.r_[1,np.cumprod(1+r)]
    cov=wcov(frame);var=weights@cov@weights
    std=np.sqrt(np.diag(cov));cm=cov/np.outer(std,std)
    active=weights>0
    eig=np.linalg.eigvalsh(cm[np.ix_(active,active)])
    contribution=weights*(cov@weights)/var
    off=np.triu_indices(len(weights),1)
    w2=(weights[:,None]*weights)[off]
    return {"n":len(frame),"start":str((frame.index[0]-pd.Timedelta(days=7)).date()),
            "end":str(frame.index[-1].date()),"return":path[-1]-1,
            "volatility":np.sqrt(var*52),"mdd":np.min(path/np.maximum.accumulate(path)-1),
            "worst_week":r.min(),"average_pair_correlation":np.average(cm[off],weights=w2) if w2.sum() else None,
            "weight_effective_count":1/(weights@weights),
            "correlation_dimensions":eig.sum()**2/(eig@eig),
            "diversification_ratio":weights@std/np.sqrt(var),
            "risk_contribution":dict(zip(frame.columns,contribution)),
            "path":[[str(d.date()),float(v)] for d,v in zip([frame.index[0]-pd.Timedelta(days=7),*frame.index],path)],
            "drawdown":[float(v) for v in path/np.maximum.accumulate(path)-1]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--date",default=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat())
    args=parser.parse_args()
    BASE=ROOT/"data/portfolio"/args.date
    POLICY=ROOT/f"research/portfolio_policy_{args.date}.json"
    if (ROOT/"publish/github-pages/reports"/args.date/"manifest.json").exists():
        raise SystemExit("Published report data is frozen. Recompute under a new date.")
    policy=read(str(POLICY.relative_to(ROOT)))
    manifest=json.loads((BASE/"nav/manifest.json").read_text())
    assert len(manifest)==30+len(policy.get("additional_nav_codes",[])) and all(r["status"]=="collected" for r in manifest)
    files={r["code"]:BASE/"nav"/(r["code"]+".csv") for r in manifest}
    data={c:pd.read_csv(p,parse_dates=["date"]).set_index("date") for c,p in files.items()}
    levels={c:f.wealth for c,f in data.items()}
    positions=read(policy["positions_path"])
    funds=[dict(p) for p in positions["positions"]]+[{"id":"noan","code":"002051","name":"诺安创新驱动C","amount_cny":0,
        "manager":"左少逸","manager_since":"2023-05-20","qdii":False,"status":"candidate_not_bought","role":"半导体/PCB候选","group":"technology"}]
    for f in funds:
        f["role"]=policy.get("role_overrides",{}).get(f["code"],f["role"])
    bycode={f["code"]:f for f in funds}
    names={r["code"]:r["product"]["name"] for r in manifest}
    refs=read("research/explorer_policy_2026-09-17.json")["references"]+[{"code":"159516","name":"半导体设备ETF","group":"technology"}]
    refcodes=[r["code"] for r in refs]
    # A report prepared during Friday must not treat that unfinished day as a full week.
    weekly_cutoff=min(pd.Timestamp(policy["nav_cutoff"]),pd.Timestamp(args.date)-pd.Timedelta(days=1))
    dates=pd.date_range(end=weekly_cutoff,periods=300,freq="W-FRI")
    wlevels={}
    for c,s in levels.items():
        union=s.index.union(dates).sort_values()
        v=s.reindex(union).ffill().reindex(dates)
        seen=pd.Series(s.index,index=s.index).reindex(union).ffill().reindex(dates)
        v[(dates-pd.DatetimeIndex(seen)).days>7]=np.nan
        wlevels[c]=v
    weekly=pd.DataFrame(wlevels).pct_change(fill_method=None)
    for c,f in bycode.items():
        weekly.loc[weekly.index-pd.Timedelta(days=7)<pd.Timestamp(f["manager_since"]),c]=np.nan
    rng=np.random.default_rng(policy["bootstrap"]["seed"])
    validation=[]
    validation_path=ROOT/f"research/portfolio_validation_{args.date}.json"
    for item in json.loads(validation_path.read_text())["points"]:
        c=item["code"];v=float(data[c].loc["2026-06-30","unit_nav"])
        assert abs(v-item["nav"])<.00011,(c,v,item["nav"])
        result={**item,"nav_passed":True}
        if "period_return_pct" in item:
            start=item.get("period_start","2025-12-31")
            actual=(levels[c].loc["2026-06-30"]/levels[c].loc[start]-1)*100
            assert abs(actual-item["period_return_pct"])<.04,(c,actual,item)
            result.update(return_passed=True,calculated_return_pct=actual)
        validation.append(result)
    secondary=[]
    for r in json.loads((BASE/"secondary/manifest.json").read_text()):
        c=r["code"];d=pd.Timestamp(r["extracted_date"])
        actual=float(data[c].loc[d,"unit_nav"]) if d in data[c].index else None
        passed=actual is not None and abs(actual-r["extracted_nav"])<.00011
        assert passed,(c,actual,r["extracted_nav"])
        secondary.append({"code":c,"date":str(d.date()),"nav":actual,"passed":passed,"url":r["url"],
                          "note":"独立发布平台；底层供数独立性未证实"})
    pairs=[]
    for a,b in combinations(bycode,2):
        for window in policy["weekly_windows"]:
            p=weekly[[a,b]].tail(window).dropna()
            down=p[(p[a]<0)&(p[b]<0)]
            bdown=p[p[b]<0]
            row={"a":a,"b":b,"window":window,"n":len(p),"weighted":corr(p) if len(p)>=20 else None,
                 "plain":float(p.corr().iloc[0,1]) if len(p)>=20 else None,
                 "second_down_n":len(bdown),"second_down_corr":corr(bdown) if len(bdown)>=8 else None,
                 "joint_down_fraction":len(down)/len(p) if len(p) else None}
            if window==52 and len(p)>=20:
                sampled=p.to_numpy()[block_indices(len(p),1000,4,rng)]
                centered=sampled-sampled.mean(axis=1,keepdims=True)
                bs=(centered[:,:,0]*centered[:,:,1]).sum(axis=1)/np.sqrt((centered[:,:,0]**2).sum(axis=1)*(centered[:,:,1]**2).sum(axis=1))
                row["plain_corr_ci90"]=np.quantile(bs,[.05,.95])
                row["ci_note"]="4周共同块重采样1000次的普通相关区间；不是加权系数置信区间。"
                row["lag_diagnostic"]={str(k):float(p[a].corr(p[b].shift(k))) for k in [-1,0,1]}
            pairs.append(row)
    # All checkpoints use only data up to that checkpoint, never today's ranking.
    checkpoint=[]
    for date in policy["checkpoint_dates"]:
        market=pd.DataFrame({c:levels[c].loc[:date] for c in refcodes}).dropna()
        cutoff=market.index[-1]
        blend=(market.iloc[-1]/market.iloc[-21]-1+market.iloc[-1]/market.iloc[-61]-1)/2
        ranks=(blend.rank(method="average")-1)/(len(refcodes)-1)*100
        market_rows=[{"code":c,"return20":float(market[c].iloc[-1]/market[c].iloc[-21]-1),
                      "return60":float(market[c].iloc[-1]/market[c].iloc[-61]-1),
                      "heat":float(ranks[c])} for c in refcodes]
        scores={}
        for c in bycode:
            correlations={}
            for ref in refcodes:
                p=weekly.loc[:date,[c,ref]].tail(26).dropna()
                if len(p)>=20:correlations[ref]=corr(p)
            pos={k:max(0,v)**2 for k,v in correlations.items() if v is not None}
            scores[c]={"market_support":sum(pos[k]*ranks[k] for k in pos)/sum(pos.values()) if len(pos)>=3 and sum(pos.values())>0 else None,
                       "references_used":len(pos),"top_link":max(correlations,key=lambda k:correlations[k]) if correlations else None}
        checkpoint.append({"date":date,"market_end":str(cutoff.date()),"market_start20":str(market.index[-21].date()),
                           "market_start60":str(market.index[-61].date()),"markets":market_rows,"funds":scores})
    rolling=[]
    chosen=[("022184","021662"),("022184","021277"),("021662","021277"),("027170","006075"),("021180","010390"),("022714","011370")]
    for a,b in chosen:
        values=[]
        for end in dates[-53:]:
            p=weekly.loc[:end,[a,b]].tail(26).dropna()
            values.append([str(end.date()),corr(p) if len(p)>=20 else None,len(p)])
        rolling.append({"a":a,"b":b,"points":values})
    held={p["code"]:p["amount_cny"] for p in funds if p["status"] in ["reported_held","subscription_reported"]}
    planned={**held,"010390":150000}
    user={**planned,"021180":170000,"010390":400000,"002051":150000}
    moderate={**planned,"021180":320000,"010390":250000,"002051":150000}
    allocations={"held":held,"planned":planned,"proposal":user,"moderate":moderate}
    scenarios=[]
    for sid,amounts in allocations.items():
        for basis in ["c_only","bocom_a"]:
            frame=pd.DataFrame({c:weekly["519696"] if c=="027170" and basis=="bocom_a" else weekly[c] for c in amounts}).dropna()
            start="2026-01-22" if basis=="bocom_a" else "2025-09-17"
            frame=frame.loc[frame.index-pd.Timedelta(days=7)>=pd.Timestamp(start)].tail(52)
            m=portfolio_metrics(frame,amounts)
            w=np.array(list(amounts.values()),float);w/=w.sum()
            r=frame.to_numpy()@w
            indexes=block_indices(len(frame),1000,4,rng)
            # Interval applies to the ordinary standard deviation, not recent-weighted vol.
            bs=r[indexes].std(axis=1,ddof=1)*np.sqrt(52)
            idx2=block_indices(len(frame),1000,2,rng)
            es_count=max(1,int(np.ceil(len(r)*.1)))
            order=np.argsort(r)[:es_count]
            tail_contribution=frame.iloc[order].mean().to_numpy()*w
            draws=rng.integers(0,len(frame)-3,size=2000)
            month=np.array([np.prod(1+r[i:i+4])-1 for i in draws])
            hist,edges=np.histogram(month,bins=18)
            m.update(id=sid,basis=basis,amounts=amounts,total_cny=sum(amounts.values()),count=len(amounts),
                plain_vol=float(r.std(ddof=1)*np.sqrt(52)),plain_vol_ci90=np.quantile(bs,[.05,.95]),
                plain_vol_ci90_block2=np.quantile(r[idx2].std(axis=1,ddof=1)*np.sqrt(52),[.05,.95]),
                worst_10pct_week_mean=float(np.sort(r)[:es_count].mean()),tail_weeks=es_count,
                tail_contribution=dict(zip(frame.columns,tail_contribution)),
                resampled_four_week={"q05":np.quantile(month,.05),"median":np.median(month),"q95":np.quantile(month,.95),
                    "worst_observed":min(np.prod(1+r[i:i+4])-1 for i in range(len(r)-3)),
                    "bins":edges,"counts":hist,"observed_overlapping_blocks":len(r)-3})
            scenarios.append(m)
    # Sequential role-constrained reductions, evaluated on the same initial common dates.
    baseframe=weekly[list(held)].dropna().tail(52)
    reductions=[]
    amounts=held.copy()
    base_metrics=portfolio_metrics(baseframe,amounts)
    basew=np.array([amounts.get(c,0) for c in baseframe.columns])/sum(amounts.values())
    baseline_returns=baseframe.to_numpy()@basew
    paired_indices=block_indices(len(baseframe),1000,4,rng)
    for i,step in enumerate(policy["pruning_steps"]):
        amount=amounts.pop(step["remove"])
        for c,fraction in step["destinations"].items():amounts[c]+=amount*fraction
        assert abs(sum(amounts.values())-2290000)<.001
        m=portfolio_metrics(baseframe,amounts)
        w=np.array([amounts.get(c,0) for c in baseframe.columns])/2290000
        rr=baseframe.to_numpy()@w
        delta=(rr[paired_indices].std(axis=1,ddof=1)-baseline_returns[paired_indices].std(axis=1,ddof=1))*np.sqrt(52)
        sensitivity_frame=pd.DataFrame({c:weekly["519696"] if c=="027170" else weekly[c] for c in held}).dropna()
        sensitivity_frame=sensitivity_frame.loc[sensitivity_frame.index-pd.Timedelta(days=7)>=pd.Timestamp("2026-01-22")]
        sens=portfolio_metrics(sensitivity_frame,amounts)
        reductions.append({**step,**m,"step":i+1,"count":len(amounts),"amounts":amounts.copy(),
            "ordinary_vol_delta_ci90":np.quantile(delta,[.05,.95]),
            "a_sensitivity_vol":sens["volatility"],"a_sensitivity_n":sens["n"]})
    # Compare removing each single holding using proportional reinvestment; avoid cash effect.
    ablations=[]
    for c in held:
        remain={k:v for k,v in held.items() if k!=c}
        factor=2290000/sum(remain.values());remain={k:v*factor for k,v in remain.items()}
        m=portfolio_metrics(baseframe,remain)
        ablations.append({"code":c,"vol_delta":m["volatility"]-base_metrics["volatility"],
                          "mdd_delta":m["mdd"]-base_metrics["mdd"],"note":"按其他基金原比例再分配；不是最优接收方案。"})
    rolemap={c:("core_growth" if c=="022714" else "core_value" if c=="022415" else
                   "global_broad" if c in ["027170","006075"] else "overseas_tech" if f["qdii"] else
                   "other" if c=="021902" else "technology") for c,f in bycode.items()}
    stress=[]
    stress_alloc={**allocations,**{f"reduce_{r['count']}":r["amounts"] for r in reductions}}
    for sid,amounts in stress_alloc.items():
        for shock in policy["stress_shocks"]:
            pieces={c:v*shock[rolemap[c]] for c,v in amounts.items()}
            stress.append({"portfolio":sid,"shock":shock["id"],"return":sum(pieces.values())/sum(amounts.values()),
                           "change_cny":sum(pieces.values()),"contribution_cny":pieces})
    # Historical event coverage: no proxy-fill for missing managers/share classes.
    events=[]
    for name,start,end in [("2022成长估值调整","2021-12-31","2022-04-29"),
                           ("2024年初小盘与流动性压力","2023-12-29","2024-02-08"),
                           ("2025年4月外部冲击","2025-04-02","2025-04-11"),
                           ("2026年夏季科技调整","2026-06-30","2026-08-31")]:
        for basis in ["actual_c","same_product_a"]:
            mapping={"022714":"519196","021662":"457001","021277":"270023","021902":"000477"} if basis=="same_product_a" else {}
            rows=[]
            for c,amt in held.items():
                proxy=mapping.get(c,c);s=levels[proxy]
                if pd.Timestamp(bycode[c]["manager_since"])>pd.Timestamp(start):continue
                first=s.loc[:start];last=s.loc[:end]
                if first.empty or last.empty:continue
                if (pd.Timestamp(start)-first.index[-1]).days>7 or (pd.Timestamp(end)-last.index[-1]).days>7:continue
                value=float(last.iloc[-1]/first.iloc[-1]-1)
                rows.append({"code":c,"series":proxy,"return":value,"amount_cny":amt,
                             "start":str(first.index[-1].date()),"end":str(last.index[-1].date())})
            covered=sum(r["amount_cny"] for r in rows)
            events.append({"name":name,"start":start,"end":end,"basis":basis,"funds":rows,"covered_amount":covered,
                           "coverage":covered/2290000,
                           "covered_subportfolio_return":sum(r["return"]*r["amount_cny"] for r in rows)/covered if covered else None,
                           "note":"仅覆盖部分的归一收益，不是完整当前组合；缺失不能填0。"})
    # Per-fund behavior summary and a sober manager-period boundary.
    current=[]
    common=pd.DataFrame({c:levels[c] for c in bycode}).dropna()
    for c,f in bycode.items():
        history=levels[c].loc[f["manager_since"]:]
        last=checkpoint[-1]["funds"][c]
        peer=weekly[[c]+[k for k in held if k!=c]].dropna().tail(52)
        other=[k for k in held if k!=c]
        ww=np.array([held[k] for k in other],float);ww/=ww.sum()
        pr=pd.Series(peer[other].to_numpy()@ww,index=peer.index)
        comparison=pd.concat([peer[c],pr],axis=1)
        observed=[q["funds"][c]["market_support"] for q in checkpoint if q["funds"][c]["market_support"] is not None]
        current.append({**f,"latest_date":str(history.index[-1].date()),"latest_nav":float(data[c].unit_nav.iloc[-1]),
            "period_start":str(history.index[0].date()),
            "daily_mdd_manager":float((history/history.cummax()-1).min()),
            "latest_support":last["market_support"],"support_range":[min(observed),max(observed)] if observed else None,
            "support_nodes":len(observed),"top_link":last["top_link"],
            "portfolio_corr":corr(comparison) if len(comparison)>=20 else None,"portfolio_corr_n":len(comparison),
            "shared_return20":float(common[c].iloc[-1]/common[c].iloc[-21]-1),
            "shared_return60":float(common[c].iloc[-1]/common[c].iloc[-61]-1)})
    input_paths=[POLICY,ROOT/policy["positions_path"],BASE/"nav/manifest.json",BASE/"secondary/manifest.json",
                 validation_path,ROOT/"research/explorer_policy_2026-09-17.json",Path(__file__)]
    # Show the unfinished week's real daily movement separately from complete-week risk.
    recent_updates=[]
    for sid,amounts in allocations.items():
        subset=common.loc[dates[-1]:]
        if len(subset)<2:
            recent_updates.append({"id":sid,"start":str(common.index[-1].date()),
                "end":str(common.index[-1].date()),"intervals":0,"return":None,"status":"awaiting_common_nav",
                "note":"最新共同净值尚不能覆盖本周，不把缺失基金记为0收益。"})
            continue
        w=np.array([amounts.get(c,0) for c in common.columns],float);w/=w.sum()
        latest_return=float((subset.iloc[-1]/subset.iloc[0]-1).to_numpy()@w)
        recent_updates.append({"id":sid,"start":str(subset.index[0].date()),"end":str(subset.index[-1].date()),
                              "intervals":len(subset)-1,"return":latest_return,
                              "note":"同日净值对齐、期初权重持有的未完整周变动；不是完整周收益或已核账户盈亏。"})
    # Latest domestic valuation interval is independent of lagged QDII disclosures.
    domestic_codes=[c for c,f in bycode.items() if not f["qdii"]]
    domestic=pd.DataFrame({c:levels[c] for c in domestic_codes}).dropna()
    event_start,event_end=domestic.index[-2],domestic.index[-1]
    event_returns={c:float(domestic[c].iloc[-1]/domestic[c].iloc[-2]-1) for c in domestic_codes}
    event_portfolios=[]
    for sid,amounts in {**allocations,"reduce_7":next(r["amounts"] for r in reductions if r["count"]==7)}.items():
        covered={c:v for c,v in amounts.items() if c in event_returns}
        change={c:v*event_returns[c] for c,v in covered.items()}
        amount=sum(covered.values())
        event_portfolios.append({"id":sid,"total_cny":sum(amounts.values()),"covered_cny":amount,
            "coverage":amount/sum(amounts.values()),"covered_change_cny":sum(change.values()),
            "covered_return":sum(change.values())/amount,"contribution_cny":change,
            "whole_portfolio_return":None,"missing_codes":[c for c in amounts if c not in covered]})
    event_reference={c:float(levels[c].loc[event_end]/levels[c].loc[event_start]-1)
                     for c in refcodes if event_end in levels[c].index and event_start in levels[c].index}
    latest_event={"start":str(event_start.date()),"end":str(event_end.date()),
        "calendar_days":int((event_end-event_start).days),"fund_returns":event_returns,
        "reference_returns":event_reference,"portfolios":event_portfolios,
        "note":"境内基金最新两个已公布净值日之间的变动，可能跨越假期；对QDII缺失部分不填0，不估算完整账户损益。"}
    # Compare with the previous frozen recommendation, not a newly optimized allocation.
    prior_files=sorted(p for p in (ROOT/"data/portfolio").glob("*/analysis.json")
                       if p.parent.name<args.date and (ROOT/"publish/github-pages/reports"/p.parent.name/"manifest.json").exists())
    period_comparison=None
    if prior_files:
        prior_path=prior_files[-1];previous=json.loads(prior_path.read_text())
        old={f["code"]:f for f in previous["funds"]}
        old_held=next(s for s in previous["scenarios"] if s["id"]=="held" and s["basis"]=="c_only")
        rows=[]
        for f in current:
            c=f["code"];anchor=old[c]["latest_date"]
            f["since_previous_nav_return"]=float(levels[c].iloc[-1]/levels[c].loc[anchor]-1)
            f["previous_nav_date"]=anchor
            rows.append({"code":c,"start":anchor,"end":f["latest_date"],
                "return":f["since_previous_nav_return"],"support_before":old[c]["latest_support"],
                "support_after":f["latest_support"]})
        # Start no earlier than publication date; do not include returns observed before the recommendation.
        after=common.loc[previous["report_date"]:]
        trials=[]
        if len(after)>=2:
            previous_count=previous["policy"].get("preferred_count",7)
            for label,amounts in [("上期11只基线",old_held["amounts"]),
                (f"上期冻结{previous_count}只方案",next(r["amounts"] for r in previous["reductions"] if r["count"]==previous_count))]:
                value=sum(v*(after[c].iloc[-1]/after[c].iloc[0]-1) for c,v in amounts.items())/sum(amounts.values())
                trials.append({"label":label,"amounts":amounts,"start":str(after.index[0].date()),
                    "end":str(after.index[-1].date()),"intervals":len(after)-1,"return":float(value)})
        period_comparison={"previous_report_date":previous["report_date"],"previous_file":str(prior_path.relative_to(ROOT)),
            "funds":rows,"frozen_followup":trials,
            "previous_weekly_end":old_held["end"],"weekly_end":str(dates[-1].date()),
            "previous_held_vol":old_held["volatility"],"current_held_vol":base_metrics["volatility"],
            "note":"基金各自起止日不同，逐只收益不能直接加总。上期方案前瞻跟踪从上期报告日后的共同净值开始，样本很短，未模拟成交费与限购。"}
        input_paths.append(prior_path)
    daily_dates={c:str(data[c].index[-1].date()) for c in data}
    output={"report_date":policy["report_date"],"generated_at":datetime.now(timezone.utc).isoformat(),
        "nav_requested_through":policy["nav_cutoff"],"nav_cutoff":max(daily_dates.values()),
        "weekly_cutoff":str(dates[-1].date()),"series_latest_dates":daily_dates,
        "latest_qdii_date":max(daily_dates[f["code"]] for f in funds if f["qdii"]),
        "recent_updates":recent_updates,"latest_event":latest_event,"period_comparison":period_comparison,"policy":policy,
        "positions":positions,"funds":current,"names":names,"references":refs,
        "checkpoints":checkpoint,"pairs":pairs,"rolling_pairs":rolling,"scenarios":scenarios,
        "reductions":reductions,"reduction_baseline":base_metrics,"ablations":ablations,"stress":stress,
        "historical_events":events,"validation":{"official":validation,"secondary":secondary,
            "series_count":len(manifest),"nav_rows":sum(r["nav"]["rows"] for r in manifest),
            "note":"13只基金均有正式披露点和独立发布平台点核验；12项阶段收益复算。参考指数基金以供应商双端点和事件调整为主，尚非所有序列独立双源全历史。"},
        "input_hashes":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths},
        "nav_hashes":{c:hashlib.sha256(p.read_bytes()).hexdigest() for c,p in files.items()},
        "shared_recent_period":{"end":str(common.index[-1].date()),"start20":str(common.index[-21].date()),"start60":str(common.index[-61].date())}}
    (BASE/"analysis.json").write_text(json.dumps(serial(output),ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps(serial({"scenarios":[{k:s[k] for k in ["id","basis","n","volatility","mdd","return","weight_effective_count","correlation_dimensions"]} for s in scenarios],
        "reductions":[{k:s[k] for k in ["count","volatility","mdd","return","ordinary_vol_delta_ci90"]} for s in reductions],
        "validation":{"official":len(validation),"secondary":len(secondary)}}),ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
