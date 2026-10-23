"""Independent quantitative checks for robust payoff ranges and conditional simulation outputs."""
import json,hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
from scipy.optimize import linprog
from analyze_portfolio import ROOT

date=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
base=ROOT/f"data/ideal_review/{date}"
f=json.loads((base/"forward.json").read_text())
intel=json.loads((base/"intelligence.json").read_text())
paths=np.load(base/"forward_paths.npz")
for name,h in f["inputs"].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
bounds=[b["weight_bounds"] for b in f["branches"]]
v=np.array(f["vertices"]);assert np.allclose(v.sum(axis=1),1) and (v>=0).all()
for i,b in enumerate(bounds):assert (v[:,i]>=b[0]-1e-8).all() and (v[:,i]<=b[1]+1e-8).all()
for item in f["robust"]:
    p=paths[item["id"]];assert p.shape==(4,f["simulations_per_branch"]) and np.isfinite(p).all()
    mean=p.mean(axis=1)
    lower=linprog(mean,A_eq=[[1,1,1,1]],b_eq=[1],bounds=bounds,method="highs")
    upper=linprog(-mean,A_eq=[[1,1,1,1]],b_eq=[1],bounds=bounds,method="highs")
    assert lower.success and upper.success
    assert np.allclose([lower.fun,-upper.fun],item["mean_range"])
    gains=v@np.maximum(p,0).mean(axis=1);losses=v@np.maximum(-p,0).mean(axis=1)
    assert np.allclose([min(gains/losses),max(gains/losses)],item["gain_loss_ratio_range"])
    for b,branch in enumerate(f["branches"]):
        r=branch["responses"][item["id"]]
        assert np.isclose(r["q10"],np.quantile(p[b],.1))
        assert np.isclose(r["expected_shortfall10"],p[b][p[b]<=r["q10"]].mean())
        assert r["q05"]<=r["q10"]<=r["median"]<=r["q90"]<=r["q95"]
        assert np.isclose(r["loss5_path_fraction"],(p[b]<=-.05).mean())
assert all(e["date"]>=date and e["verified"] for e in f["events"])
assert all(r["published_on"]<=date for r in intel["items"])
assert f["estimation"]["end"]<=date
for e in intel["items"]:
    if e["source_id"].startswith("announcement_") and e["source_id"].split("_")[-1] in ["002611","010390"]:
        assert not any(n in e["title"] for n in ["东方精工","冠昊生物"])
result={"passed":True,"date":date,"checks":["线性规划独立验证最差/最好期望","所有分支权重闭合且有界","条件模拟分位与尾部独立复算","事件/公告时间不穿越","基金公告接口避免股票代码碰撞","来源与模型输入哈希一致"],
        "probability_status":"not_calibrated"}
(base/"forward_verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
