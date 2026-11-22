"""Build the current review layer without rewriting the immutable historical report."""
import json,hashlib,os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PUBLIC=Path(os.environ.get("RESEARCH_PUBLIC_ROOT",ROOT.parents[0])).resolve()
SITE=PUBLIC/"proposals/2026-11-21/asymmetry"

def main():
    template=ROOT/"report/asymmetry-v11-frozen.html"
    if not template.exists():raise FileNotFoundError("Missing immutable V1.1 template")
    html=template.read_text()
    html=html.replace('</style>',(ROOT/"report/asymmetry-current.css").read_text()+'\n</style>',1)
    html=html.replace('<section class="chapter" id="verdict">',(ROOT/"report/asymmetry-current.html").read_text()+'\n<section class="chapter" id="verdict">',1)
    html=html.replace('<a href="#verdict"><span class="num">01</span>判断</a>','<a href="#current"><span class="num">00</span>当日审视</a><a href="#verdict"><span class="num">01</span>历史判断</a>',1)
    html=html.replace('DOC100独立审议版','每日审视 · 宏观优先版',1)
    html=html.replace('HOLDER RESEARCH / 001 · V1.1','HOLDER RESEARCH / 001 · V1.2',1)
    html=html.replace('<title>非对称 · DOC100独立审议与230万配置复核</title>',
                      '<title>非对称 · 每日宏观市场审视与现金预算</title>',1)
    html=html.replace('先看 230 万方案','先看当日宏观与现金',1)
    html=html.replace('href="#portfolio">先看当日宏观与现金','href="#current">先看当日宏观与现金',1)
    html=html.replace('研究截点：境内净值 11.20 / QDII 净值 11.19',
                      '历史基线：境内净值 11.20 / QDII 11.19；最新审视见00',1)
    # Every old chapter receives a visible historical scope label.
    import re
    html=re.sub(r'(<section class="chapter(?: [^"]*)?" id="(?!current)[^"]+">)',
       r'\1<p class="historical-label">2026.11.21历史基线 · 原日期保留 · 当下判断须对照00最新审视及每日修正</p>',html)
    html=html.replace('</body></html>','<script>\n'+(ROOT/"report/asymmetry-current.js").read_text()+'\n</script>\n</body></html>',1)
    SITE.mkdir(parents=True,exist_ok=True)
    (SITE/"index.html").write_text(html)
    policy=SITE/"daily-policy";policy.mkdir(exist_ok=True)
    for name in ["decision-20261122.json","macro-cash-20261122.md"]:
        shutil.copyfile(ROOT/"research"/name,policy/name)
    shutil.copyfile(ROOT/"research/asymmetry-daily-policy.json",policy/"policy.json")
    manifest_path=SITE/"manifest.json";manifest=json.loads(manifest_path.read_text())
    manifest["revision"]="V1.2";manifest["current_review_date"]="2026-11-22"
    manifest["daily_automation"]="source evidence plus GitHub Models semantic and counter-review; no automatic trading"
    for f in [SITE/"index.html",*policy.iterdir()]:
        manifest["files"][str(f.relative_to(SITE))]={"bytes":f.stat().st_size,"sha256":hashlib.sha256(f.read_bytes()).hexdigest()}
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print("Built current macro-first layer and preserved the historical V1.1 source.")

if __name__=="__main__":main()
