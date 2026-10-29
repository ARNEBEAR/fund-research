"""Fresh NAV archive for the screenshot's exact target portfolio."""
import json,hashlib,os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collect_history import ROOT,collect_nav,collect_product

date=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
policy=json.loads((ROOT/f"research/ideal_policy_{date}.json").read_text())
base=ROOT/f"data/ideal_review/{date}"
if (Path(os.environ.get("RESEARCH_PUBLIC_ROOT",ROOT/"publish/github-pages"))/f"reports/{date}/manifest.json").exists():
    raise SystemExit("Published date: do not overwrite its data.")
raw=base/"nav/raw";raw.mkdir(parents=True,exist_ok=True)
rows=[]
config=json.loads((ROOT/"research/daily_config.json").read_text())
factor_codes=config.get("forward_factor_model",{}).get("factor_codes",[])
codes=list(dict.fromkeys([p["code"] for p in policy["positions"]]+policy["extra_codes"]+factor_codes))
assert sum(p["amount_cny"] for p in policy["positions"])==policy["total_cny"]
for c in codes:
    try:
        frame,row=collect_nav(c,"2021-01-01",date,raw,c in set(["510300","515880","512480","512720","510880"]+factor_codes)-{"006075","002611"})
        product=collect_product(c,raw,frame)
        assert not product["same_vendor_mismatches"],c
        assert product["history_row_count_matches_api"],c
        row.update(status="collected",product=product,
                   csv_sha256=hashlib.sha256((base/"nav"/f"{c}.csv").read_bytes()).hexdigest())
    except Exception as exc:
        row={"code":c,"status":"failed","error":str(exc)}
    rows.append(row)
    (base/"nav/manifest.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    print(c,row.get("product",{}).get("name"),row["status"],row.get("last_date"),row.get("latest_nav"),flush=True)
