"""Run inside the extracted dataset directory: python3 recompute.py (numpy, pandas)."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
D=json.loads((ROOT/"analysis.json").read_text())
frames={c["code"]:pd.read_csv(ROOT/"evidence"/(c["code"]+".csv"),index_col=0,parse_dates=True)
        for c in D["cards"]}
checked=0
for comparison in D["comparisons"].values():
    codes=sorted({c for p in comparison["portfolios"].values() for c in p["weights"]})
    panel=pd.concat({c:frames[c]["wealth"] for c in codes},axis=1).dropna()
    for policy in comparison["portfolios"].values():
        weights=pd.Series(policy["weights"])
        for window,expected in policy["metrics"].items():
            if expected is None:continue
            part=panel.loc[expected["start"]:expected["end"],list(weights.index)]
            path=(part/part.iloc[0]).mul(weights).sum(axis=1)
            values={"return_pct":(path.iloc[-1]-1)*100,
                    "mdd_pct":(path/path.cummax()-1).min()*100,
                    "vol_pct":path.pct_change().dropna().std(ddof=1)*np.sqrt(252)*100}
            for key,value in values.items():
                assert abs(value-expected[key])<1e-7,(policy["name"],window,key,value,expected[key])
                checked+=1
        assert abs(weights.sum()-1)<1e-10
assert all(len(c["axes"])==5 and round(sum(c["axes"])/5)==c["score"] for c in D["cards"])
print(json.dumps({"passed":True,"metric_values_checked":checked,"funds":len(frames),"manual_scores_not_statistical_models":True}))
