"""Prepare a new immutable research date using the frozen target and current registry."""
import json,os,shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=Path(os.environ.get("RESEARCH_PUBLIC_ROOT",ROOT/"publish/github-pages")).resolve()
date=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
if (PUBLIC/f"reports/{date}/manifest.json").exists():
    print("Already published",date);raise SystemExit(0)
config=json.loads((ROOT/"research/daily_config.json").read_text())
policy=json.loads((ROOT/config["target_template"]).read_text())
registry=json.loads((PUBLIC/"reports/index.json").read_text())
earlier=[r for r in registry if r["date"]<date and r.get("type")=="target_portfolio_review"]
if earlier:
    previous=earlier[0]["date"]
    dest=ROOT/f"data/ideal_review/{previous}/analysis.json"
    dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists():shutil.copyfile(PUBLIC/earlier[0]["path"]/"analysis.json",dest)
    policy["previous_review_date"]=previous
else:policy.pop("previous_review_date",None)
policy["date"]=date
policy["source"]="10月19日用户截图目标；每日规则研究保持目标冻结，未记为成交。"
dest=ROOT/f"research/ideal_policy_{date}.json"
if not dest.exists():dest.write_text(json.dumps(policy,ensure_ascii=False,indent=2))
base=ROOT/f"data/ideal_review/{date}";base.mkdir(parents=True,exist_ok=True)
print("Prepared",date,"previous",policy.get("previous_review_date"))
