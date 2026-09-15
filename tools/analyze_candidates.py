"""Role assessments and descriptive external-candidate counterfactuals."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_history import path_metrics, weekly_levels, weighted_corr

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/candidates/2026-09-10"


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def score(ratings, weights):
    if set(ratings) != set(weights) or not np.isclose(sum(weights.values()), 1):
        raise ValueError("Invalid score dimensions or weights")
    if any(not np.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError("Score weights must be finite and nonnegative")
    if any(v is not None and (not isinstance(v, (int, float)) or not np.isfinite(v) or not 0 <= v <= 5)
           for v in ratings.values()):
        raise ValueError("Invalid ordinal rating")
    if any(v is None for v in ratings.values()):
        return None
    return float(20 * sum(ratings[k] * weights[k] for k in weights))


def corr(a, b, half_life):
    pair = pd.concat([a, b], axis=1).dropna()
    if len(pair) < 8 or (pair.std() <= 0).any():
        return None
    return weighted_corr(pair, half_life)[0]


def load(code, current=True, cutoff="2026-09-08"):
    folder = ROOT / "data/history/2026-09-08" if current else BASE / "nav"
    path = folder / (code + ".csv")
    frame = pd.read_csv(path, parse_dates=["date"]).set_index("date").loc[:cutoff]
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    assert frame.wealth.notna().all() and (frame.wealth > 0).all()
    return frame.wealth.rename(code), path


def levels_from_returns(returns, anchor, initial_cost=0):
    assert 0 <= initial_cost < 1
    result = (1 + returns).cumprod() * (1 - initial_cost)
    return pd.concat([pd.Series([1.0], index=[anchor]), result])


def main():
    policy = read("research/candidate_policy.json")
    decision = read("research/decision_policy.json")
    experiment = read("research/experiment.json")
    holdings = read("data/holdings.json")
    config = policy["comparison"]
    notes = read("research/candidate_notes.json")
    profiles = {p["id"]: p for p in read("research/manager_profiles.json")["profiles"]}
    current = {c["id"]: c["code"] for c in experiment["candidates"]}
    weights = {h["id"]: float(h["weight_pct"]) for h in holdings["holdings"] if h["id"] in current}
    weight_sum = sum(weights.values())
    assert np.isclose(weight_sum, 76.6)
    levels, paths = {}, []
    for code in current.values():
        levels[code], path = load(code, cutoff=policy["nav_as_of"])
        paths.append(path)
    nav_manifest = read("data/candidates/2026-09-10/nav/manifest.json")
    for item in nav_manifest:
        if item["status"] != "collected":
            raise ValueError("Uncollected candidate: " + item["code"])
        assert not item["product"]["same_vendor_mismatches"]
        assert item["external_point"] is None or item["external_point"]["passed"]
        levels[item["code"]], path = load(item["code"], False, policy["nav_as_of"])
        paths.append(path)
    weekly = pd.concat([weekly_levels(series, policy["nav_as_of"], config["max_nav_age_days"])
                        for series in levels.values()], axis=1).dropna()
    assert weekly.index[-1] == pd.Timestamp("2026-09-04")
    comparison_rows = []
    for c in policy["candidates"]:
        if not c["collect_nav"]:
            continue
        target = current[c["replaces"]]
        shared = pd.concat([levels[c["code"]], levels[target]], axis=1).dropna()
        returns = {}
        for n in [20, 60, 120]:
            frame = shared.tail(n + 1)
            if len(frame) != n + 1:
                continue
            growth = frame.iloc[-1] / frame.iloc[0] - 1
            returns[str(n)] = {
                "start": str(frame.index[0].date()), "end": str(frame.index[-1].date()),
                "candidate": float(growth[c["code"]]), "target": float(growth[target]),
                "difference_pp": float((growth[c["code"]] - growth[target]) * 100),
            }
        annual = []
        for year in range(2022, 2027):
            start = pd.Timestamp(year=year - 1, month=12, day=31)
            prior = levels[c["code"]].loc[:start]
            year_levels = levels[c["code"]].loc[levels[c["code"]].index.year == year]
            if not len(year_levels) or not len(prior):
                continue
            frame = pd.concat([prior.tail(1), year_levels])
            metrics = path_metrics(frame)
            annual.append({"year": year, **metrics, "partial_year": year == 2026,
                           "start": str(frame.index[0].date()), "end": str(frame.index[-1].date()),
                           "current_manager_period": str(frame.index[0].date()) >= c["manager_since"]})
        windows = []
        for n in config["trailing_weeks"]:
            frame = weekly.tail(n + 1)
            if len(frame) != n + 1:
                raise ValueError("Insufficient common weekly sample")
            rets = frame.pct_change(fill_method=None).dropna()
            base_weights = pd.Series({current[k]: v / weight_sum for k, v in weights.items()})
            base_returns = rets[base_weights.index] @ base_weights
            target_weight = base_weights[target]
            replacement_returns = base_returns + target_weight * (rets[c["code"]] - rets[target])
            tech_ids = [i for i in config["technology_sleeve"] if i != c["replaces"]]
            tech_weights = pd.Series({current[i]: weights[i] for i in tech_ids})
            tech_weights /= tech_weights.sum()
            tech_returns = rets[tech_weights.index] @ tech_weights
            down = tech_returns < 0
            base_path = levels_from_returns(base_returns, frame.index[0])
            base = path_metrics(base_path, 52)
            simulated = []
            for bps in config["switch_cost_stress_bps"]:
                path = levels_from_returns(replacement_returns, frame.index[0], target_weight * bps / 10000)
                metrics = path_metrics(path, 52)
                simulated.append({"cost_bps": bps, "return": metrics["return"],
                                  "max_drawdown": metrics["max_drawdown"],
                                  "difference_pp": 100 * (metrics["return"] - base["return"])})
            pair_daily = shared.loc[frame.index[0]:frame.index[-1]]
            pair_metrics = {
                k: path_metrics(levels[k].loc[pair_daily.index[0]:pair_daily.index[-1]])
                for k in [c["code"], target]
            }
            windows.append({
                "weeks": n, "start": str(frame.index[0].date()), "end": str(frame.index[-1].date()),
                "candidate_corr_tech": corr(rets[c["code"]], tech_returns, config["half_life_weeks"]),
                "target_corr_tech": corr(rets[target], tech_returns, config["half_life_weeks"]),
                "candidate_corr_qianhai": corr(rets[c["code"]], rets[current["qianhai"]], config["half_life_weeks"]),
                "candidate_down_corr": corr(rets.loc[down, c["code"]], tech_returns[down], config["half_life_weeks"]),
                "target_down_corr": corr(rets.loc[down, target], tech_returns[down], config["half_life_weeks"]),
                "down_weeks": int(down.sum()),
                "daily_pair_start": str(pair_daily.index[0].date()),
                "daily_pair_end": str(pair_daily.index[-1].date()),
                "candidate_daily_mdd": pair_metrics[c["code"]]["max_drawdown"],
                "target_daily_mdd": pair_metrics[target]["max_drawdown"],
                "base_return": base["return"], "base_weekly_mdd": base["max_drawdown"],
                "base_volatility": float(base_returns.std(ddof=1) * np.sqrt(52)),
                "replacement_volatility": float(replacement_returns.std(ddof=1) * np.sqrt(52)),
                "replacement_weight_pct_in_sleeve": float(target_weight * 100),
                "scenarios": simulated,
            })
        comparison_rows.append({**c, "notes": notes[c["id"]],
                                "target_name": profiles[c["replaces"]]["short"],
                                "original_account_weight_pct": weights[c["replaces"]],
                                "returns": returns, "windows": windows, "annual": annual})
    scores = []
    for item in decision["decisions"]:
        raw = score(item["ratings"], decision["weights"])
        sensitivity = {label: score(item["ratings"], weights)
                       for label, weights in decision["sensitivity_weights"].items()}
        band = next((b["label"] for b in decision["bands"] if raw is not None and raw >= b["min"]), "职责未定义")
        values = [raw] + list(sensitivity.values())
        scores.append({**item, "name": profiles[item["id"]]["short"],
                       "role_name": profiles[item["id"]]["role"],
                       "code": current[item["id"]], "weight": weights[item["id"]],
                       "score": None if raw is None else int(np.floor(raw + 0.5)),
                       "raw_score": raw, "band": band, "weight_sensitivity": sensitivity,
                       "sensitivity_range": None if raw is None else [min(values), max(values)]})
    catalogue = read("data/candidates/2026-09-10/catalogue.json")
    catalogue.pop("rows")
    inputs = paths + [ROOT / p for p in [
        "research/candidate_policy.json", "research/decision_policy.json",
        "research/candidate_sources.json", "research/candidate_notes.json", "research/manager_profiles.json",
        "research/experiment.json", "data/holdings.json",
        "data/candidates/2026-09-10/catalogue.json", "data/candidates/2026-09-10/nav/manifest.json",
        "data/candidates/2026-09-10/sources/manifest.json", "tools/analyze_candidates.py",
    ]]
    out = {
        "date": policy["screened_on"], "nav_as_of": policy["nav_as_of"],
        "decision_policy": decision, "scores": scores, "candidate_policy": policy,
        "catalogue": catalogue, "comparisons": comparison_rows,
        "excluded": [{**c, "notes": notes[c["id"]]} for c in policy["candidates"] if not c["collect_nav"]],
        "candidate_series": len(nav_manifest), "candidate_nav_rows": sum(x["nav"]["rows"] for x in nav_manifest),
        "external_points": [x["external_point"] for x in nav_manifest if x["external_point"]],
        "account_coverage_pct": weight_sum, "full_account_simulation": False,
        "proven_superior_candidates": 0, "trade_recommendations_generated": False,
        "input_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
    }
    target = BASE / "assessment.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print("Role scores:", [(x["id"], x["score"], x["sensitivity_range"]) for x in scores])
    for row in comparison_rows:
        w = row["windows"][-1]
        print(row["name"], "corr tech", round(w["candidate_corr_tech"], 3),
              "target", round(w["target_corr_tech"], 3), "corr qianhai", round(w["candidate_corr_qianhai"], 3),
              "return impact pp", round(w["scenarios"][1]["difference_pp"], 3),
              "vol", round(w["base_volatility"] * 100, 2), round(w["replacement_volatility"] * 100, 2))


if __name__ == "__main__":
    main()
