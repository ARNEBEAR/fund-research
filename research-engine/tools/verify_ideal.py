"""Independent checks and secondary NAV publication matching for the screenshot study."""
import json,re,hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from analyze_portfolio import ROOT
from archive_deep_sources import archive

date=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
base=ROOT/f"data/ideal_review/{date}"
x=json.loads((base/"analysis.json").read_text())
folder=base/"secondary";folder.mkdir(exist_ok=True)
rows=[]
for pos in x["policy"]["positions"]+[{"code":"000217","name":"华安黄金ETF联接C敏感性"}]:
    c=pos["code"]
    item={"id":"sina_"+c,"code":c,"title":pos["name"]+" 新浪净值核验","publisher":"新浪财经",
          "url":"https://stock.finance.sina.com.cn/fundInfo/view/FundInfo_JJGK.php?symbol="+c,"date":date}
    contradiction=False
    try:
        result=archive(item,folder)
        text=(folder/(item["id"]+".txt")).read_text()
        m=re.search(r"单位净值\s*[:：]\s*([\d.]+)",text)
        d=re.search(r"截止日期\s*[:：]\s*(\d{4}/\d\d?/\d\d?)",text)
        assert m and d
        when=pd.Timestamp(d.group(1))
        nav=float(m.group(1))
        s=pd.read_csv(base/"nav"/f"{c}.csv",parse_dates=["date"]).set_index("date")
        result.update(date_observed=str(when.date()),nav=nav,passed=bool(abs(s.loc[when,"unit_nav"]-nav)<.00011))
        contradiction=not result["passed"]
        if contradiction:result.update(contradiction=True,error="Same-date NAV contradicts secondary publication")
    except Exception as exc:result={**item,"passed":False,"error":str(exc),"contradiction":contradiction}
    rows.append(result)
    (folder/"manifest.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    print(c,result["passed"],result.get("date_observed"),flush=True)
minimum=11
config_path=ROOT/"research/daily_config.json"
if config_path.exists():minimum=json.loads(config_path.read_text()).get("minimum_independent_nav_points",11)
assert not any(r.get("contradiction") for r in rows),"Conflicting same-date NAV; publication blocked."
assert sum(r["passed"] for r in rows)>=minimum
for filename,h in x["inputs"].items():assert hashlib.sha256((ROOT/filename).read_bytes()).hexdigest()==h
for filename,h in x.get("nav_hashes",{}).items():assert hashlib.sha256((ROOT/filename).read_bytes()).hexdigest()==h
amounts={p["code"]:p["amount_cny"] for p in x["policy"]["positions"]}
assert sum(amounts.values())==2468000
assert np.isclose(sum(x["groups"].values()),1)
assert np.isclose(sum(x["weekly"]["risk_contributions"].values()),1)
codes=list(dict.fromkeys(c for r in x["weekly"]["results"] for c in r["amounts"]))
levels={c:pd.read_csv(base/"nav"/f"{c}.csv",parse_dates=["date"]).set_index("date").wealth for c in codes}
dates=pd.to_datetime(x["weekly"]["paths"]["dates"])
vals={}
for c,s in levels.items():
    vals[c]=[s.iloc[s.index.searchsorted(d,side="right")-1] for d in dates]
values=pd.DataFrame(vals,index=dates)
returns=values/values.shift(1)-1
returns=returns.dropna()
assert len(returns)==x["weekly"]["n"] and len(returns)>=20
if x.get("latest_event"):
    event=x["latest_event"]
    assert (event["whole_portfolio_return"] is None)==bool(event["missing_codes"])
    assert event["covered_cny"]==sum(amounts[c] for c in event["fund_returns"])
    assert np.isclose(event["change_cny"],sum(amounts[c]*r for c,r in event["fund_returns"].items()))
    assert np.isclose(event["covered_return"],event["change_cny"]/event["covered_cny"])
    assert sorted(event["missing_codes"])==sorted(c for c in amounts if c not in event["fund_returns"])
if x.get("previous_review"):
    previous=json.loads((ROOT/x["previous_review"]["file"]).read_text())
    assert previous["policy"]["positions"]==x["policy"]["positions"]
    assert previous["policy"]["scenarios"]==x["policy"]["scenarios"]
    if x["previous_review"]["followup"]:
        assert x["previous_review"]["followup"]["start"]>=previous["date"]
    else:
        common_dates=pd.DataFrame({c:pd.read_csv(base/"nav"/f"{c}.csv",parse_dates=["date"]).set_index("date").wealth for c in amounts}).dropna().index
        assert len(common_dates[common_dates>=previous["date"]])<2
for plan in x["weekly"]["results"]:
    assert np.isclose(sum(plan["amounts"].values()),2468000)
    r=sum(returns[c]*v/2468000 for c,v in plan["amounts"].items())
    path=np.r_[1,(1+r).cumprod()]
    assert np.isclose(np.std(r,ddof=1)*np.sqrt(52),plan["vol"])
    assert np.isclose(np.min(path/np.maximum.accumulate(path)-1),plan["mdd"])
    assert np.isclose(path[-1]-1,plan["return"])
for scenario in x["scenarios"]:
    for window,response in scenario["fund_responses"].items():
        result=sum(response[c]*v/2468000 for c,v in amounts.items())
        assert np.isclose(result,scenario["plans"]["target"]["by_window"][window])
        assert response["002611"]==scenario["gold"]
        assert response["006075"]==scenario["sp500"]
        for c in [k for k in amounts if k not in ["006075","002611"]]:
            fit=x["fits"][c][window]
            assert fit["end"]<=date
            b=fit["coef"]
            expected=b["sp500"]*scenario["sp500"]+b["market"]*scenario["market"] if c=="027170" else (
                b["market"]*scenario["market"]+b["technology_excess"]*(scenario["communication"]-scenario["market"])+
                b["value_excess"]*(scenario["dividend"]-scenario["market"]))
            assert np.isclose(expected,response[c])
# The new fund's half-year disclosure NAV and return must agree with reconstructed history.
s=pd.read_csv(base/"nav/519697.csv",parse_dates=["date"]).set_index("date")
assert abs(s.loc["2026-06-30","unit_nav"]-5.892)<.00011
# Published unit NAVs have three decimals. A 1.53bp difference in the
# half-year return must be assessed against their actual rounding bounds.
# This period has one distribution, 0.188 per share on January 15.
start=float(s.loc["2025-12-31","unit_nav"])
end=float(s.loc["2026-06-30","unit_nav"])
ex_div=float(s.loc["2026-01-15","unit_nav"])
distribution=.188
assert np.isclose(s.loc["2026-01-15","cumulative_nav"]-s.loc["2026-01-15","unit_nav"]
                  -(s.loc["2026-01-14","cumulative_nav"]-s.loc["2026-01-14","unit_nav"]),distribution)
calc=end/start*(1+distribution/ex_div)-1
assert np.isclose(calc,s.loc["2026-06-30","wealth"]/s.loc["2025-12-31","wealth"]-1)
rounding_low=(end-.0005)/(start+.0005)*(1+distribution/(ex_div+.0005))-1
rounding_high=(end+.0005)/(start-.0005)*(1+distribution/(ex_div-.0005))-1
assert rounding_low<=.3038<=rounding_high
result={"passed":True,"date":date,"secondary_points":sum(r["passed"] for r in rows),
        "secondary_missing":[r["code"] for r in rows if not r["passed"]],
        "checks":["截图金额精确闭合246.8万","同日期与重建路径独立核验","所有全额配置与风险贡献合计","交银优势中报点位和阶段收益","情景逐只加总、不外推截距",f'{sum(r["passed"] for r in rows)}个另一发布平台净值点一致'],
        "bocom_advantage_h1":{"official_return":.3038,"reconstructed_return":calc,
                              "published_nav_rounding_range":[rounding_low,rounding_high],
                              "note":"三位净值及0.188元分红重建收益与官方相差约1.53bp，在净值公布精度范围内相容，不宣称逐位相等。"},
        "limits":"净值历史主要来自同一供应商，另一发布平台不等于底层供数独立；未称全历史双源独立核验。"}
(base/"verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
