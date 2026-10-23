"""Replay latest frozen numeric inputs in a fresh checkout and validate the portable engine."""
import json,os,zipfile,shutil
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from analyze_portfolio import ROOT

public=Path(os.environ["RESEARCH_PUBLIC_ROOT"])
registry=json.loads((public/"reports/index.json").read_text())
latest=registry[0]["date"]
assert latest==datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
with zipfile.ZipFile(public/registry[0]["path"]/"dataset.zip") as z:
    for item in z.infolist():
        path=Path(item.filename)
        assert not path.is_absolute() and ".." not in path.parts
        if item.filename.startswith(("data/","research/")):
            dest=ROOT/path
            dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():dest.write_bytes(z.read(item))
latest_data=ROOT/f"data/ideal_review/{latest}"
if not (latest_data/"forward_paths.npz").exists():
    raise RuntimeError("Frozen report package does not contain forward path evidence.")
print("Restored cold-run evidence",latest)
