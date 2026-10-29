"""Publish the reviewed screenshot target into the existing dated research archive."""
import argparse,hashlib,json,re,shutil,zipfile,os
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=Path(os.environ.get("RESEARCH_PUBLIC_ROOT",ROOT/"publish/github-pages")).resolve()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pct(v):return f"{v*100:+.2f}%"
def wan(v):return f"{v/10000:.2f}万元"
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--date",default=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat())
    parser.add_argument("--revise-current",action="store_true")
    args=parser.parse_args();date=args.date
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}",date)
    base=ROOT/f"data/ideal_review/{date}"
    analysis=json.loads((base/"analysis.json").read_text())
    notes=json.loads((ROOT/f"research/ideal_notes_{date}.json").read_text())
    check=json.loads((base/"verification.json").read_text())
    assert notes["review_status"]=="reviewed_current_data" and notes["reviewed_on"]==date
    assert analysis["date"]==date and check["passed"]
    sources=json.loads((base/"sources/manifest.json").read_text())
    assert all(s["status"]=="archived" for s in sources)
    sources=[{k:s[k] for k in ["id","title","url","date","publisher","kind"]} for s in sources]
    registry_path=PUBLIC/"reports/index.json";registry=json.loads(registry_path.read_text())
    old=next((r for r in registry if r["date"]==date),None)
    if old and (not args.revise_current or date!=max(r["date"] for r in registry)):
        raise SystemExit("Dated report exists; only explicitly revise the latest report.")
    target=PUBLIC/"reports"/date;target.mkdir(parents=True,exist_ok=True)
    # Publish only the research inputs, never raw conversation text or screenshot location.
    extra={}
    for key in ["forward","intelligence","forward_verification"]:
        if (base/f"{key}.json").exists():extra[key]=json.loads((base/f"{key}.json").read_text())
    if "forward" in extra:assert extra["forward_verification"]["passed"]
    payload={"analysis":analysis,"notes":notes,"sources":sources,**extra}
    html=(ROOT/"report/ideal-template.html").read_text()
    quarter_date=notes.get("quarter_review_date")
    quarter_html=""
    if quarter_date:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}",quarter_date) and quarter_date<=date
        quarter_html=f'<section id="quarter-review"><span class="label">三季报深度复核 · {quarter_date}</span><h2>持仓变了，经理评价也要更新</h2><p class="intro">{escape(notes["quarter_review_summary"])}</p><a class="text-link" href="../{quarter_date}/quarterly.html">查看逐只经理、三期持仓变化与情景关系 ↗</a></section>'
    html=html.replace("<!-- QUARTER_REVIEW -->",quarter_html)
    for key,value in {"DATE":date,"HEADLINE":notes["headline"],"VERDICT":notes["verdict"],"SCOPE":notes["scope"],
                      "GOLD_JUDGMENT":notes["gold_judgment"],"SIMPLIFICATION_JUDGMENT":notes["simplification_judgment"],
                      "METHOD_LIMIT":notes["method_limit"],"DATA_QUALITY":notes["data_quality"]}.items():
        html=html.replace("{{"+key+"}}",escape(value))
    for marker,value in {"/* BASE_CSS */":(ROOT/"report/portfolio.css").read_text(),
                         "/* IDEAL_JS */":(ROOT/"report/ideal.js").read_text(),
                         "/* ECHARTS_VENDOR */":(ROOT/"report/vendor/echarts.min.js").read_text(),
                         "/* IDEAL_DATA */":json.dumps(payload,ensure_ascii=False,separators=(",",":"),allow_nan=False).replace("<","\\u003c")}.items():
        assert html.count(marker)==1
        html=html.replace(marker,value.replace("</script","<\\/script"))
    assert "{{" not in html
    (target/"index.html").write_text(html)
    for name,value in [("analysis.json",analysis),("notes.json",notes),("methodology.json",analysis["policy"]),("sources.json",sources),("verification.json",check)]:
        (target/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    for name,value in extra.items():(target/f"{name}.json").write_text(json.dumps(value,ensure_ascii=False,indent=2))
    quarter_base=ROOT/f"data/quarter_review/{date}"
    if (quarter_base/"review.html").exists():
        for src,dst in [("review.html","quarterly.html"),("review.md","quarterly.md"),
                        ("review.json","quarterly.json"),("review-data.zip","quarterly-data.zip")]:
            shutil.copyfile(quarter_base/src,target/dst)
    labels={"target":"截图目标","no_gold":"无黄金，其余按比例分配","gold_6%":"黄金6%","gold_20%":"黄金20%","eight_role_merge":"8项敏感性变体","old_reported_scaled":"9月17日旧口径，同额比例放大"}
    positions=analysis["policy"]["positions"];latest={r["code"]:r for r in analysis["latest"]}
    event=analysis["latest_event"];prev=analysis["previous_review"]
    lines=[f"# 目标组合与最新判断 · {date}","",notes["headline"],"",notes["verdict"],"",notes["scope"],"",
           f'境内与黄金正式净值至{event["end"]}，QDII至{latest["006075"]["date"]}，完整周截止{analysis["weekly"]["cutoff"]}，全组合共同日频至{analysis["daily"]["end"]}。',"",
           "## 当前判断与最新证据","",notes["current_judgment"],"",
           f'{event["start"]}—{event["end"]}已覆盖目标{wan(event["covered_cny"])}（{event["coverage"]*100:.1f}%），这部分{pct(event["covered_return"])}，目标金额静态映射{wan(event["change_cny"])}；缺失同日QDII不填0，不是全账户损益。',""]
    if "forward" in extra:
        f=extra["forward"];intel=extra["intelligence"]
        lines += ["## 未来20日：事件、条件盈亏与尾部","",f["weight_rule"],
                  "盈亏比为假设权重下正收益期望/负收益绝对值期望；不是市场真实赔率。","",
                  "| 方案 | 人工权重期望响应范围 | 条件盈亏比范围 |","|---|---:|---:|"]
        for r in f["robust"]:
            lines += [f'| {labels[r["id"]]} | {pct(r["mean_range"][0])}～{pct(r["mean_range"][1])} | {r["gain_loss_ratio_range"][0]:.2f}～{r["gain_loss_ratio_range"][1]:.2f} |']
        if f["breakeven_bull_vs_bear"] is not None:
            lines += ["",f'只比较修复/增长担忧两分支时，盈亏平衡需要修复权重约{f["breakeven_bull_vs_bear"]*100:.1f}%；不是预计上涨概率。',""]
        for e in intel["events"]:lines += [f'- {e["date"]} [{e["name"]}]({e["source"]})：正向 {e["positive"]}；反向 {e["negative"]}。']
        lines += ["","| 分支 | 目标模拟中位数 | 路径收益10/90分位 | 最差10%路径平均收益 |","|---|---:|---:|---:|"]
        for b in f["branches"]:
            r=b["responses"]["target"]
            lines += [f'| {b["name"]} | {pct(r["median"])} | {pct(r["q10"])} / {pct(r["q90"])} | {pct(r["expected_shortfall10"])} |']
        lines += ["","分位数包含历史参数和残差扰动，不是未来置信区间。事件改变冲击时点，不凭空提升预期收益。","",
                  "### 新情报与证据等级",""]
        for i in intel["items"][:12]:lines += [f'- {i["published_on"]} [{i["title"]}]({i["url"]})：{i["status"]}。']
        lines += ["",f'情报覆盖{intel["coverage"]["ok"]}/{intel["coverage"]["total"]}路；不可用源不补造。',""]
    for row in notes["changes"]:lines += [f'**{row["title"]}**：{row["text"]}',""]
    if quarter_date:
        lines += [f'## 三季报深度复核 · {quarter_date}',"",notes["quarter_review_summary"],"",
                  f'[逐只经理、三期持仓与情境推演](../{quarter_date}/quarterly.html)',""]
    if prev and not prev["followup"]:
        lines += [f'{prev["date"]}冻结目标之后尚无足够共同净值形成前瞻成绩。逐只新增净值与建议发布后的实际跟踪分开。',""]
    lines += ["## 目标持仓与处理倾向","","| 名称 / 代码 | 目标金额 | 比例 | 最新净值日 | 当前判断 |","|---|---:|---:|---|---|"]
    for p in positions:
        action=notes["actions"][p["code"]]
        lines += [f'| {p["name"]} / {p["code"]}{"（代理）" if p.get("proxy") else ""} | {wan(p["amount_cny"])} | {p["amount_cny"]/2468000*100:.2f}% | {latest[p["code"]]["date"]} | {action["action"]}；{action["reason"]} |']
    lines += ["","金额合计246.80万元。交银优势未核到独立C类，不伪造份额；黄金和标普未指定最终产品，只是回测代理。","",
              "## 同额配置的收益与风险","","| 方案 | 普通年化波动 | 周频最大回撤 | 样本累计收益 |","|---|---:|---:|---:|"]
    for r in analysis["weekly"]["results"]:
        lines += [f'| {labels[r["id"]]} | {r["vol"]*100:.2f}% | {pct(r["mdd"])} | {pct(r["return"])} |']
    lines += ["",f'{analysis["weekly"]["start"]}—{analysis["weekly"]["cutoff"]}共同{analysis["weekly"]["n"]}周，按周恢复权重。旧已报229万元比例放大，只作参照，不复原用户实盘。周频遗漏部分峰谷，最大回撤不是损失上限。',
              f'共同日频每日恢复权重：年化波动{analysis["daily"]["vol"]*100:.2f}%、回撤{pct(analysis["daily"]["mdd"])}；周频不再平衡敏感性：波动{analysis["buyhold"]["vol"]*100:.2f}%、回撤{pct(analysis["buyhold"]["mdd"])}。',
              f'交银环球独立A类敏感性限制新团队后{analysis["a_sensitivity"]["n"]}周，不拼接C类：波动{analysis["a_sensitivity"]["vol"]*100:.2f}%、回撤{pct(analysis["a_sensitivity"]["mdd"])}。',""]
    risk=analysis["weekly"]["risk_contributions"]
    lines += [f'万家、产业、科益、华商原分组占资金{analysis["groups"]["domestic_technology"]*100:.2f}%，共同样本方差贡献{sum(risk[c] for c in ["022714","021180","010390","011370"])*100:.1f}%；科益＋华商贡献{(risk["010390"]+risk["011370"])*100:.1f}%。分组不等于穿透科技占比；这是历史方差分解，不是未来损失比例。',"",
              "## 黄金与精简的取舍","",notes["gold_judgment"],"","| 窗口 | 黄金/科技相关 | 科技下跌周 | 黄金同跌周 | 这些周黄金平均收益 |","|---|---:|---:|---:|---:|"]
    for r in analysis["gold_evidence"]:
        lines += [f'| {r["window"]}周 | {r["correlation_tech"]:.3f} | {r["technology_down_weeks"]} | {r["both_down_weeks"]} | {pct(r["gold_mean_when_tech_down"])} |']
    lines += ["",notes["simplification_judgment"],"",
              "8项变体：交银优势15.11万并入广发主题、交银环球15.11万并入标普。主题变为约14.3%、标普约18.4%，提高单经理及美国权益权重，违反截图主题约20万上限；只作敏感性，未替换原目标。","",
              "## 未来一个月的条件赔率","",notes["method_limit"],"",
              "| 人工条件 | 沪深300/通信/红利/人民币标普/黄金 | 目标响应 | 金额映射 |","|---|---|---:|---:|"]
    for s in analysis["scenarios"]:
        r=s["plans"]["target"]
        assumptions=" / ".join(pct(s[k]) for k in ["market","communication","dividend","sp500","gold"])
        lines += [f'| {s["name"]} | {assumptions} | {pct(r["min"])}～{pct(r["max"])} | {wan(r["min_cny"])}～{wan(r["max_cny"])} |']
    lines += ["","不外推回归常数；范围只反映历史窗口，不含全部残差、非线性或交易成本，不是收益预测区间。科益长窗口可能使用同一独立任期样本，不称独立证据。不能从人工冲击商数制造真实赔率或上涨概率。",""]
    for r in notes["outlook"]:lines += [f'**{r["title"]}**：{r["text"]}',""]
    lines += ["较严厉情景可能损失约20万元，且并非最坏上限。不能保证未来一个月亏损小于5%。","",
              "## 方法、数据与追溯","",notes["data_quality"],"",analysis["policy"]["method"],"",analysis["policy"]["scenario_method"],""]
    lines += analysis["policy"]["limitations"]
    lines += ["","所有模型结果基于目标方案，当前账户未连接。此前分批和5%边界为纪律示例，未证明最优。","",
              "[10月13日完整持仓与调仓时点报告](../2026-10-13/) · [数据下载](dataset.zip) · [计算JSON](analysis.json) · [哈希清单](manifest.json)","","## 来源",""]
    lines += [f'- [{s["title"]}]({s["url"]})（{s["date"]}，{s["kind"]}）' for s in sources]
    (target/"report.md").write_text("\n".join(lines))
    local=ROOT/"report/portfolio"/date;local.mkdir(parents=True,exist_ok=True)
    local_markdown=(target/"report.md").read_text()
    for relative in ["dataset.zip","analysis.json","manifest.json","../2026-10-13/"]:
        url="https://arnebear.github.io/fund-research/reports/2026-10-13/" if relative.startswith("../") else f"https://arnebear.github.io/fund-research/reports/{date}/{relative}"
        local_markdown=local_markdown.replace("]("+relative+")","]("+url+")")
    (local/"report.md").write_text(local_markdown)
    shutil.copyfile(target/"index.html",local/"index.html")
    (ROOT/f"report/ideal-portfolio-odds-{date}.md").write_text(local_markdown)
    inputs=[base/"analysis.json",base/"verification.json",base/"nav/manifest.json",base/"secondary/manifest.json",base/"sources/manifest.json",
            ROOT/f"research/ideal_policy_{date}.json",ROOT/f"research/ideal_notes_{date}.json",ROOT/f"research/ideal_sources_{date}.json",
            ROOT/"tools/analyze_ideal.py",ROOT/"tools/analyze_portfolio.py",ROOT/"tools/collect_ideal.py",ROOT/"tools/collect_history.py",
            ROOT/"tools/verify_ideal.py",ROOT/"tools/archive_deep_sources.py",ROOT/"data/positions_2026-09-17.json"]
    if prev:inputs += [ROOT/prev["file"]]
    if extra:
        inputs += [base/f"{key}.json" for key in extra]
        inputs += [p for p in [ROOT/"research/daily_config.json",ROOT/"tools/analyze_forward.py",ROOT/"tools/collect_intelligence.py",ROOT/"tools/verify_forward.py",ROOT/"tools/daily_research.py",base/"forward_paths.npz"] if p.exists()]
    with zipfile.ZipFile(target/"dataset.zip","w",zipfile.ZIP_DEFLATED) as z:
        for p in inputs+list((base/"nav").glob("*.csv")):
            z.write(p,str(p.relative_to(ROOT)))
        for p in (base/"sources").glob("*"):
            if p.suffix in [".json",".txt"] and p.name!="manifest.json":z.write(p,str(p.relative_to(ROOT)))
        for p in (base/"intelligence").glob("*"):
            if p.suffix in [".json",".txt"]:z.write(p,str(p.relative_to(ROOT)))
    input_templates=[ROOT/"report/ideal-template.html",ROOT/"report/ideal.js",ROOT/"report/portfolio.css",ROOT/"report/home-template.html",Path(__file__)]
    manifest={"date":date,"type":"target_portfolio_review","built_at":datetime.now(timezone.utc).isoformat(),
              "revision":old.get("revision",1)+1 if old else 1,"nav_cutoff":event["end"],"latest_qdii_date":latest["006075"]["date"],
              "weekly_cutoff":analysis["weekly"]["cutoff"],"positions_date":"2026-09-17","target_feedback_date":"2026-10-19",
              "status":"published_research_not_trades","html_sha256":digest(target/"index.html"),
              "files":{p.name:digest(p) for p in target.iterdir() if p.is_file() and p.name!="manifest.json"},
              "source_hashes":{str(p.relative_to(ROOT)):digest(p) for p in inputs+input_templates}}
    (target/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    entry={"date":date,"path":f"reports/{date}/","title":"目标组合 · 最新判断与条件赔率","type":"target_portfolio_review",
           "nav_cutoff":event["end"],"revision":manifest["revision"],"html_sha256":manifest["html_sha256"]}
    registry=[r for r in registry if r["date"]!=date]+[entry];registry.sort(key=lambda r:r["date"],reverse=True)
    registry_path.write_text(json.dumps(registry,ensure_ascii=False,indent=2))
    archive="".join(f'<a class="archive-row" href="{escape(r["path"])}"><time>{r["date"]}</time><span>{escape(r["title"])}</span><b>↗</b></a>' for r in registry)
    home=(ROOT/"report/home-template.html").read_text().replace("<!-- REPORT_ARCHIVE -->",archive)
    for key,value in {"LATEST_PATH":registry[0]["path"],"LATEST_DATE":registry[0]["date"],"LATEST_HEADLINE":notes["headline"],
                      "LATEST_SUMMARY":"246.80万元目标组合：最新净值、共同风险、黄金与精简取舍、未来一月条件推演。目标配置和实际持仓分开，旧结论按日期保留。"}.items():
        home=home.replace("{{"+key+"}}",escape(value))
    assert "{{" not in home
    (PUBLIC/"archive.html").write_text(home)
    latest_path=registry[0]["path"]
    (PUBLIC/"index.html").write_text(f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>ARNEBEAR · 最新基金研究</title></head><body style="background:#090b0d;color:#edf2f1;font:16px sans-serif;padding:32px"><p><a style="color:#98e1c3" href="{latest_path}">打开最新报告 · {date}</a> · <a style="color:#98e1c3" href="archive.html">日期档案</a></p><script>
const legacy=new Set(["rotation-review","current-review","fund-explorer","huashang","assessment","alternatives","managers","disclosures","synergy","history","decisions","method","sources","trade-transactions","current-fund-actions","rotation-comparison","rotation-facts","rotation-cost"]);
const h=location.hash;const d=new URLSearchParams(location.search).get("date");
if(legacy.has(h.slice(1)))location.replace("research-2026-09-20.html"+h);
else if(d&&/^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(d))fetch("reports/index.json",{{cache:"no-store"}}).then(r=>r.json()).then(rows=>{{const chosen=rows.find(r=>r.date===d);location.replace(chosen?chosen.path:"{latest_path}");}}).catch(()=>location.replace("{latest_path}"));
else location.replace("{latest_path}"+h);
</script></body></html>''')
    (PUBLIC/"site-manifest.json").write_text(json.dumps({"updated_on":date,"home_sha256":digest(PUBLIC/"index.html"),"latest_report":entry,"archive":registry},ensure_ascii=False,indent=2))
    (PUBLIC/"build.json").write_text(json.dumps({"generated_on":date,"type":"archive_home","sha256":digest(PUBLIC/"index.html"),"latest_report":entry},ensure_ascii=False,indent=2))
    (PUBLIC/"README.md").write_text(f"""# ARNEBEAR · 基金研究档案

入口：https://arnebear.github.io/fund-research/

最新报告：https://arnebear.github.io/fund-research/reports/{date}/

本期按用户截图中的246.80万元/10项目标配置研究，不当作已成交或当前市值。境内与黄金正式净值至{event["end"]}，QDII至{latest["006075"]["date"]}，完整周截止{analysis["weekly"]["cutoff"]}。

报告包含最新判断、目标职责、共同风险、黄金0/6/12.24/20%同额敏感性、8项精简变体与四组条件情景。概率未校准，模型窗口范围不是未来收益置信区间。标普与黄金使用明确标注的C类代理，交银优势不伪造C类。

日期目录包含HTML、Markdown、计算JSON、方法、核验、来源、CSV/脚本包及SHA-256。原有报告和搜索专题保持原链接；旧口径回放不能解释账户实际年度收益。每日08:20北京时间自动规则研究，09:20同日失败补偿；GitHub调度可能延迟，同日首次成功后冻结。没有账户连接或自动交易。默认最新报告，顶部手动切换日期。

经用户授权公开发布研究；不包含原始对话、账户凭据或原始报告PDF。noindex不是访问控制。
""")
    print(json.dumps({"report":str(target),"sha256":manifest["html_sha256"],"revision":manifest["revision"]}))

if __name__=="__main__":main()
