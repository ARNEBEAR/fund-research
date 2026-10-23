"""Cache public fund NAVs and parse JSON literals without executing provider JS."""

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
API = "https://api.fund.eastmoney.com/f10/lsjz"


def json_literal(text, name):
    match = re.search(r"\bvar\s+" + re.escape(name) + r"\s*=\s*", text)
    if not match:
        raise ValueError("Missing JSON literal: " + name)
    return json.JSONDecoder().raw_decode(text[match.end():])[0]


def fetch(url, path):
    if path.exists():
        return path.read_bytes()
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; LocalFundResearch/1.0)",
        "Referer": "https://fundf10.eastmoney.com/",
    })
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as response:
                data = response.read()
                content_type = response.headers.get("Content-Type")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            meta = {
                "url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                "content_type": content_type, "source_family": "eastmoney",
            }
            path.with_suffix(path.suffix + ".meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            time.sleep(0.12)
            return data
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def collect_nav(code, start, end, folder, is_reference=False):
    text = fetch(
        "https://fund.eastmoney.com/pingzhongdata/" + code + ".js",
        folder / (code + "_product.js"),
    ).decode("utf-8-sig")
    if json_literal(text, "fS_code") != code:
        raise ValueError("Product code mismatch: " + code)
    frame = pd.DataFrame(json_literal(text, "Data_netWorthTrend"))
    cumulative_data = pd.DataFrame(json_literal(text, "Data_ACWorthTrend"), columns=["x", "cumulative"])
    frame = frame.merge(cumulative_data, on="x", how="left", validate="one_to_one").sort_values("x")
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame["x"], unit="ms", utc=True)).tz_convert(
        "Asia/Shanghai"
    ).tz_localize(None).normalize()
    frame.index.name = "date"
    frame = frame.loc[start:end]
    if frame.empty or frame.index.has_duplicates:
        raise ValueError("Empty or duplicate NAV history: " + code)
    nav = pd.to_numeric(frame["y"], errors="coerce")
    cumulative = pd.to_numeric(frame["cumulative"], errors="coerce")
    reported = pd.to_numeric(frame["equityReturn"], errors="coerce") / 100
    if nav.isna().any() or (nav <= 0).any() or not np.isfinite(nav).all():
        raise ValueError("Invalid unit NAV: " + code)
    if reported.iloc[1:].isna().any() or (reported.dropna() <= -1).any():
        raise ValueError("Invalid provider returns: " + code)
    dividend_increment = (cumulative - nav).diff()
    exact = (nav + dividend_increment.clip(lower=0)) / nav.shift(1) - 1
    mismatch = (exact - reported).abs() > 0.00011
    special = (dividend_increment < -0.0002) | mismatch | exact.isna()
    if is_reference:
        returns = reported.copy()
        method = pd.Series("vendor_rounded_reference_return", index=frame.index)
    else:
        returns = exact.where(~special, reported)
        method = pd.Series(
            np.where(special, "vendor_rounded_event_return", "nav_plus_dividend_increment"),
            index=frame.index,
        )
    # The first observation has no comparable preceding NAV in this extract.
    returns.iloc[0] = 0.0
    if returns.isna().any() or not np.isfinite(returns).all() or (returns <= -1).any():
        raise ValueError("Invalid reconstructed return series")
    result = pd.DataFrame({
        "unit_nav": nav, "cumulative_nav": cumulative, "return": returns,
        "provider_return": reported, "method": method,
        "distribution_note": frame["unitMoney"],
    })
    result["wealth"] = (1 + result["return"]).cumprod()
    result.to_csv(folder.parent / (code + ".csv"), float_format="%.12g")
    issue_dates = [d.strftime("%Y-%m-%d") for d in frame.index[special][1:]]
    return result, {
        "code": code, "rows": len(frame),
        "first_date": frame.index.min().strftime("%Y-%m-%d"),
        "last_date": frame.index.max().strftime("%Y-%m-%d"),
        "latest_nav": float(nav.iloc[-1]),
        "return_method": "vendor_rounded" if is_reference else "NAV plus dividend; flagged event fallback",
        "event_fallback_dates": issue_dates,
        "independently_verified_full_history": False,
    }


def collect_product(code, folder, frame):
    path = folder / (code + "_product.js")
    text = fetch("https://fund.eastmoney.com/pingzhongdata/" + code + ".js", path).decode("utf-8-sig")
    if json_literal(text, "fS_code") != code:
        raise ValueError("Product code mismatch: " + code)
    name = json_literal(text, "fS_name")
    params = {
        "fundCode": code, "pageIndex": 1, "pageSize": 20,
        "startDate": frame.index.min().strftime("%Y-%m-%d"),
        "endDate": frame.index.max().strftime("%Y-%m-%d"),
    }
    api_data = json.loads(fetch(
        API + "?" + urlencode(params), folder / (code + "_nav_sample20.json")
    ))
    if not api_data.get("Data"):
        raise ValueError("Empty NAV sample: " + code)
    points = pd.DataFrame(api_data["Data"]["LSJZList"])
    points.index = pd.to_datetime(points["FSRQ"])
    points = pd.to_numeric(points["DWJZ"])
    common = frame["unit_nav"].to_frame("product").join(points.rename("api"), how="inner")
    if common.empty:
        raise ValueError("NAV sample dates do not overlap: " + code)
    differences = common[(common["api"] - common["product"]).abs() > 0.00011]
    allocation = json_literal(text, "Data_assetAllocation")
    return {
        "code": code, "name": name, "allocation": allocation,
        "history_row_count_matches_api": len(frame) == api_data["TotalCount"],
        "api_reported_history_rows": api_data["TotalCount"],
        "same_vendor_nav_crosscheck_rows": len(common),
        "same_vendor_mismatches": [
            {"date": d.strftime("%Y-%m-%d"), "api": float(v["api"]), "product": float(v["product"])}
            for d, v in differences.iterrows()
        ],
        "crosscheck_note": "API and product JS belong to the same vendor, not independent evidence.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "research/experiment.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    folder = ROOT / "data/history" / config["as_of"] / "raw"
    folder.mkdir(parents=True, exist_ok=True)
    manifest, products = [], []
    references = {x["code"] for x in config["style_references"]}
    codes = {x["code"] for x in config["candidates"]} | references
    codes |= {x["long_code"] for x in config["candidates"] if x.get("long_code")}
    for code in sorted(codes):
        frame, item = collect_nav(code, config["history_start"], config["as_of"], folder, code in references)
        product = collect_product(code, folder, frame)
        manifest.append(item)
        products.append(product)
        print(code, product["name"], item["rows"], item["first_date"], item["last_date"],
              "same-vendor mismatches:", len(product["same_vendor_mismatches"]), flush=True)
    result = {
        "as_of": config["as_of"], "collected_at": datetime.now(timezone.utc).isoformat(),
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "series": manifest, "products": products,
        "note": "Raw NAV evidence; the two endpoints are one vendor family. No account return inferred.",
    }
    (folder.parent / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
