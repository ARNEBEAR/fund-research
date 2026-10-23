"""Idempotent daily research runner. Failed data never becomes a new latest report."""
import json,os,subprocess,sys,traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=Path(os.environ.get("RESEARCH_PUBLIC_ROOT",ROOT/"publish/github-pages")).resolve()
date=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
config=json.loads((ROOT/"research/daily_config.json").read_text())

def run(name):
    print("STEP",name,flush=True)
    subprocess.run([sys.executable,str(ROOT/"tools"/name)],cwd=ROOT,check=True)

def create_notes():
    base=ROOT/f"data/ideal_review/{date}"
    a=json.loads((base/"analysis.json").read_text());f=json.loads((base/"forward.json").read_text())
    intel=json.loads((base/"intelligence.json").read_text())
    notes=json.loads((ROOT/config["notes_template"]).read_text())
    target=next(r for r in f["robust"] if r["id"]=="target")
    weak=target["mean_range"][0]<0
    near=[e for e in intel["events"] if (datetime.fromisoformat(e["date"])-datetime.fromisoformat(date)).days<=10]
    notes.update(review_status="reviewed_current_data",reviewed_on=date,review_method="自动规则研究及数据校验，不冒充当日人工或大模型复核",
                 headline="先控制损失，再等待兑现。" if weak else "赔率改善，仍保留风险边界。",
                 verdict=("目标结构保留，科技卫星不扩张。未来20个工作日的情景权重敏感性仍包含负收益；没有足够证据支持一次性增加科技或黄金。"
                          if weak else "目标结构保留；当前人工情景范围内的收益损失交换改善，但概率未校准，不据此自动提高仓位。"),
                 current_judgment=("临近"+"、".join(e["name"] for e in near)+"，先比较盈利与利率的相反结果；"
                                   if near else "未来事件日期覆盖有限，保留正反分支并扩大判断余地；")+
                                  "公司经营回应与已实现盈利分开，情报原文及未核实项在下方列出。近期下跌不直接决定未来方向。",
                 scope="246.80万元截图目标，未记为已成交。旧持仓只作对照，目标回放不等于账户实际收益。",
                 method_limit="分支权重为人工范围。盈亏比、模拟分位数和损失路径比例只在该假设集内成立，不是已校准的市场预测。",
                 gold_judgment="黄金可能缓冲增长担忧，也可能与股票一起承受实际利率上行。12.24%不是最佳权重证明；先比较不同黄金比例的短期损失和机会成本。",
                 simplification_judgment="8项变体减少两只交银、增加广发主题与标普；会改变单经理及美国资产预算，仅供比较。",
                 data_quality=f"净值22条逐条校验，另一发布平台核对见数据页。情报本期成功{intel['coverage']['ok']}/{intel['coverage']['total']}路；失败源明确标记，不补造信息。")
    notes["changes"]=[
        {"title":"未来事件","text":"、".join(e["date"]+" "+e["name"] for e in near) if near else "暂无已核实的10日内日历事件；以新增正式披露更新。"},
        {"title":"条件盈亏","text":f"人工权重范围下，目标20日期望响应{target['mean_range'][0]*100:.1f}%～{target['mean_range'][1]*100:.1f}%；不是实际期望收益预测。"},
        {"title":"执行倾向","text":"维持截图目标为研究基准；不因标题利好临时加科技，黄金建仓与资产预算分别判断。"}
    ]
    notes["outlook"]=[
        {"title":"盈利兑现","text":"核订单能否转化为收入、利润和现金流，以及云厂商下一期投入指引；经营正常不等于超预期。"},
        {"title":"利率路径","text":"实际利率回落有利于成长与黄金；再次上行时保留股金共跌分支。"},
        {"title":"调整边界","text":"只有目标约束、经理方法或盈利逻辑发生可核实变化才修改战略预算；价格偏离用于既定再平衡。"}
    ]
    paused=intel.get("availability",{}).get("state")=="paused" if intel.get("availability") else False
    notes["actions"]["006075"]={"action":"暂停申购，先核可买渠道" if paused else "核实实际可买产品与额度",
                               "reason":"当日公开代销状态"+("显示暂停申购。" if paused else "未足以确认蚂蚁额度。")+"不以纳指或科技基金静默替代标普，不把30.22万目标当成已可执行。"}
    for code,action in notes["actions"].items():
        up=next(b for b in f["branches"] if b["id"]=="bull")["fund_responses"][code]["mean"]
        stress=next(b for b in f["branches"] if b["id"]=="rates")["fund_responses"][code]["mean"]
        action["forward_response"]={"repair":up,"rates_stress":stress}
    (ROOT/f"research/ideal_notes_{date}.json").write_text(json.dumps(notes,ensure_ascii=False,indent=2))
    sources=[]
    for source in intel["sources"]:
        if source["status"]!="ok":continue
        sources.append({"id":source["id"],"title":source.get("name",source.get("title","公开来源")),
                        "url":source["url"],"date":source.get("date",date),"publisher":source.get("rank","public"),
                        "kind":source.get("type","公告与情报原文"),"status":"archived"})
    (base/"sources").mkdir(exist_ok=True)
    (base/"sources/manifest.json").write_text(json.dumps(sources,ensure_ascii=False,indent=2))
    (ROOT/f"research/ideal_sources_{date}.json").write_text(json.dumps(sources,ensure_ascii=False,indent=2))

def main():
    status_path=PUBLIC/"automation-status.json"
    prev=json.loads(status_path.read_text()) if status_path.exists() else {}
    status={"schedule":config["schedule_local"],"timezone":config["timezone"],
            "attempted_at":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "last_success":prev.get("last_success"),"workflow":"https://github.com/ARNEBEAR/fund-research/actions/workflows/daily-research.yml"}
    if (PUBLIC/f"reports/{date}/manifest.json").exists():
        status.update(state="current_date_frozen",last_success=date)
        status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2))
        print("Already published; unchanged",date);return
    try:
        run("prepare_daily.py");run("collect_ideal.py")
        data=json.loads((ROOT/f"data/ideal_review/{date}/nav/manifest.json").read_text())
        for row in data:
            assert row["status"]=="collected"
            assert (datetime.fromisoformat(date)-datetime.fromisoformat(row["last_date"])).days<=config["max_nav_age_days"]
        run("analyze_ideal.py");run("collect_intelligence.py");run("analyze_forward.py")
        run("verify_ideal.py");run("verify_forward.py")
        create_notes()
        run("build_ideal_site.py")
        status.update(state="generated_and_verified",last_success=date)
    except Exception as exc:
        status.update(state="failed_keep_previous",error=type(exc).__name__,detail=str(exc)[:300])
        status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2))
        traceback.print_exc();raise
    status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2))
    print(json.dumps(status,ensure_ascii=False))

if __name__=="__main__":main()
