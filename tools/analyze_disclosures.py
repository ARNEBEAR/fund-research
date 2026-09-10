"""Reproducible, exploratory disclosure-date diagnostics; no trade signals."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/disclosure_analysis/2026-09-08"


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def load_levels(code, cutoff):
    for folder in ("data/history/2026-09-08", "data/style_history/2026-09-08"):
        path = ROOT / folder / (code + ".csv")
        if path.exists():
            frame = pd.read_csv(path, parse_dates=["date"]).set_index("date")
            frame = frame.loc[:cutoff]
            assert frame.index.is_unique and frame.index.is_monotonic_increasing
            assert (frame.wealth > 0).all() and np.isfinite(frame.wealth).all()
            return frame.wealth.rename(code), path
    raise FileNotFoundError(code)


def shared_returns(fund, reference):
    # Intersect levels BEFORE differencing, so both returns span identical dates.
    levels = pd.concat([fund.rename("fund"), reference.rename("reference")], axis=1).dropna()
    return levels, levels.pct_change(fill_method=None).dropna()


def diagnose(fund, reference, published, pre_n, min_post, hac_lags, max_post=60):
    if fund.index[0] > pd.Timestamp(published):
        return {"status": "fund_not_live_at_disclosure", "n_post": 0, "n_pre": 0}, []
    levels, returns = shared_returns(fund, reference)
    eligible = levels.index[levels.index >= pd.Timestamp(published)]
    if len(eligible) < 2:
        return {"status": "no_post_data", "n_post": 0, "n_pre": 0}, []
    anchor = eligible[0]
    pre = returns.loc[returns.index <= anchor].tail(pre_n)
    post = returns.loc[returns.index > anchor].head(max_post)
    row = {
        "status": "insufficient_sample",
        "start": str(anchor.date()),
        "end": str(post.index[-1].date()),
        "n_pre": len(pre),
        "n_post": len(post),
        "fund_return": float((1 + post.fund).prod() - 1),
        "reference_return": float((1 + post.reference).prod() - 1),
        "pre_start": str(pre.index[0].date()) if len(pre) else None,
    }
    row["difference_pp"] = 100 * (row["fund_return"] - row["reference_return"])
    chart_levels = levels.loc[pre.index[0] if len(pre) else anchor : post.index[-1]]
    normalized = chart_levels.div(levels.loc[anchor]).sub(1).mul(100)
    chart = [
        [str(date.date()), float(values.fund), float(values.reference)]
        for date, values in normalized.iterrows()
    ]
    if len(pre) < pre_n or len(post) < min_post:
        return row, chart
    combined = pd.concat([pre, post])
    flag = (combined.index > anchor).astype(float)
    x = combined.reference.to_numpy()
    design = np.column_stack([np.ones(len(x)), x, flag, x * flag])
    if np.linalg.matrix_rank(design) != 4:
        row["status"] = "singular_model"
        return row, chart
    model = sm.OLS(combined.fund.to_numpy(), design).fit(
        cov_type="HAC", cov_kwds={"maxlags": hac_lags, "use_correction": True}
    )
    before = sm.OLS(pre.fund, sm.add_constant(pre.reference)).fit()
    after = sm.OLS(post.fund, sm.add_constant(post.reference)).fit()
    interval = model.conf_int(alpha=0.05)[3]
    row.update(
        status="estimated",
        beta_pre=float(model.params[1]),
        beta_post=float(model.params[1] + model.params[3]),
        beta_change=float(model.params[3]),
        beta_change_ci95=[float(interval[0]), float(interval[1])],
        p_value=float(model.pvalues[3]),
        correlation_pre=float(pre.fund.corr(pre.reference)),
        correlation_post=float(post.fund.corr(post.reference)),
        r2_pre=float(before.rsquared),
        r2_post=float(after.rsquared),
        residual_vol_post=float(after.resid.std(ddof=1)),
    )
    return row, chart


def events_for(candidate, deep, legacy, evidence):
    fund_id = candidate["id"]
    events = []
    for item in deep["reports"]:
        if item.get("fund_id") == fund_id and item.get("period_end"):
            events.append({**item, "path": "data/deep_research/" + item["id"] + ".pdf"})
    for item in legacy:
        if item["id"].startswith(fund_id + "_"):
            events.append({**item, "fund_id": fund_id})
    for item in evidence["sources"]:
        if item["id"] == fund_id + "_h1":
            events.append({**item, "id": fund_id + "_2026h1", "fund_id": fund_id,
                           "path": item["local_path"]})
    return sorted(events, key=lambda event: event["published_on"])


def main():
    cfg = read_json("research/style_study.json")
    candidates = read_json("research/experiment.json")["candidates"]
    deep = read_json("research/deep_sources.json")
    legacy = read_json("data/reports/manifest.json")
    evidence = read_json("data/evidence.json")
    references = {
        row["code"]: row["name"]
        for row in read_json("research/experiment.json")["style_references"] + cfg["new_series"]
    }
    codes = {c["code"] for c in candidates}
    codes.update(cfg["domestic_references"] + cfg["overseas_references"])
    levels, paths = {}, {}
    for code in sorted(codes):
        levels[code], paths[code] = load_levels(code, cfg["as_of"])
    results, events, charts = [], {}, {}
    for c in candidates:
        refs = cfg["overseas_references"] if c["qdii"] else cfg["domestic_references"]
        for event in events_for(c, deep, legacy, evidence):
            events[event["id"]] = event
            for ref in refs:
                for pre_n in cfg["pre_observations"]:
                    row, chart = diagnose(
                        levels[c["code"]], levels[ref], event["published_on"], pre_n,
                        cfg["minimum_post_observations"], cfg["hac_lags"],
                    )
                    row.update(fund_id=c["id"], code=c["code"], reference=ref,
                               event_id=event["id"], pre_window=pre_n)
                    results.append(row)
                    if pre_n == max(cfg["pre_observations"]):
                        charts[event["id"] + ":" + ref] = chart
    families = {}
    for pre_n in cfg["pre_observations"]:
        selected = [r for r in results if r["pre_window"] == pre_n and r["status"] == "estimated"]
        rejected, adjusted, _, _ = multipletests(
            [r["p_value"] for r in selected], alpha=cfg["false_discovery_rate"], method="fdr_bh"
        )
        for row, q, reject in zip(selected, adjusted, rejected):
            row.update(q_value=float(q), exploratory_flag=bool(reject))
        families[str(pre_n)] = {"tests": len(selected), "flags": int(rejected.sum())}
    # Check the newly used fund quarter returns against formal reports.
    q2_reported = {
        "wanjia": 28.37, "qianhai": -3.80, "efunds": 114.41,
        "invesco": 68.94, "bocom": 33.27, "franklin": 66.06,
        "guangfa_global": 55.88, "guangfa_theme": -4.03, "bosera": 12.39,
    }
    checks = []
    for c in candidates:
        series = levels[c["code"]]
        actual = float((series.loc["2026-06-30"] / series.loc["2026-03-31"] - 1) * 100)
        expected = q2_reported[c["id"]]
        passed = abs(actual - expected) <= 0.03
        checks.append({"fund_id": c["id"], "calculated_pct": actual,
                       "reported_pct": expected, "tolerance_pp": 0.03, "passed": passed})
    if not all(check["passed"] for check in checks):
        raise ValueError("Quarter return validation failed: " + json.dumps(checks))
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in paths.values()}
    for path in ["research/style_study.json", "research/deep_sources.json",
                 "research/experiment.json", "data/reports/manifest.json", "data/evidence.json"]:
        hashes[path] = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    hashes["tools/analyze_disclosures.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output = {
        "as_of": cfg["as_of"], "generated_on": "2026-09-10",
        "method": cfg, "post_observation_cap": 60,
        "contractual_daily_benchmark_available": False,
        "post_cap_note": "First 60 post-anchor shared intervals at most; recent events end at cutoff.",
        "reference_names": references, "events": events, "results": results, "charts": charts,
        "multiple_testing_families": families, "quarter_validation": checks,
        "input_sha256": hashes,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "study.json").write_text(json.dumps(output, ensure_ascii=False, indent=2,
                                              allow_nan=False), encoding="utf-8")
    pd.DataFrame(results).to_csv(OUT / "diagnostics.csv", index=False)
    print(json.dumps({"events": len(events), "families": families,
                      "quarter_checks_passed": len(checks)}, ensure_ascii=False))
    for row in results:
        if (row["event_id"].endswith("2026q2") and row["pre_window"] == 60
                and row["reference"] == cfg["fund_focus_reference"][row["fund_id"]]):
            print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
