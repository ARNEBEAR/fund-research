"""Build long-term mandates and comparable facts; retain dated stage proposals."""
import json,hashlib,os,re,shutil
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
PUBLIC=Path(os.environ.get("RESEARCH_PUBLIC_ROOT",ROOT.parent)).resolve()
SITE=PUBLIC/"proposals/2026-11-21/asymmetry"

def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    soup=BeautifulSoup((ROOT/"report/asymmetry-v11-frozen.html").read_text(),"html.parser")
    data=json.loads(soup.select_one("#research-data").string)
    dec=json.loads((ROOT/"research/decision-20261122-v13.json").read_text())
    passive=json.loads((ROOT/"research/independent-passive-20261122.json").read_text())
    dec["passiveSources"]=[{"title":"易方达110020官方产品与费率","url":"https://www.efunds.com.cn/fund/110020_org.shtml"},
                          {"title":"博时513500官方产品","url":"https://www.bosera.com/fund/513500.html"},
                          {"title":"513500一级申赎清单","url":"https://www.bosera.com/fund/etfList.do?fundCode=513500"}]
    dec["passiveLimit"]="110020截至11.20零售申赎开放；标准交易费对短期不利。513500正式净值截至11.19，11.20清单一级申购关闭/赎回开放，二级市场溢价、成交与券商费用未核。U60为条件替代。"
    dec["scope"]="previous dated 1-3 month stage proposals; not current long-term preference"
    for p in dec["plans"].values():
        p["title"]=p["title"].replace("当前首选","旧阶段提案")
    stage_names={"D60":"60%现金＋五基金：阶段防守","D70":"70%现金＋五基金：加强防守","R40":"40%现金＋五基金：参与修复"}
    for ident,p in dec["plans"].items():
        p["title"]=stage_names.get(ident,p["title"])
    data["currentDecision"]=dec
    longterm=json.loads((ROOT/"research/longterm-comparison-20261122.json").read_text())
    data["longtermDecision"]=longterm
    for card in data["managerCards"]:
        if card["code"]=="021902":
            card["tenure"]="2023.11.01加入共管；2024.01.04吴兴武离任后独管；C类2024.07.25新增。旧产品与共管段单列，不认证三年全独管。"
            card["longterm"]="V1.4原文纠错：独管从2024.01.04起，不是加入日2023.11.01。中加旧产品的长周期估值、选股与套保是机制提示，不能当作广发C持续实绩。2026Q2 C类−4.03%、基准+5.35%，经理承认非科技资产共同下跌超出预想；1.70%显性C运作费已入净值，长期A/C成本另核。低权益时的机会成本与收费一起检验。"
        if card["code"]=="011066":
            card["tenure"]="刘旭2015.07.29加入共管；徐彦2018.09.11离任后独管。高鑫由高新技术产业2025.01.14变更注册，同基金但合同调整；C类官方业绩从2021.01.11起算。"
            card["longterm"]="V1.4纠错：高鑫与高新技术产业法律产品连续，但2025变更注册同时修改合同；A/C、共管/独管与合同阶段分开。Q3官方C五年+35.49%、基准−2.16%，A七年可作独管产品提示而非C七年实绩。2026Q2 C类−5.68%、基准+10.17%，并非每阶段抗跌。合同股票80%—95%，制造与出口、集中和约120亿元产品容量持续核；1.80%C显性运作费已入净值，长期A/C成本另核。"
            card["source"]="https://pdf.dfcfw.com/pdf/H2_AN202610271830979356_1.pdf"
    data["independentCandidates"]=passive
    data["extra_watch_codes"]=[{"code":"110020","name":"易方达沪深300ETF联接A","product_kind":"fund"},
                              {"code":"513500","name":"博时标普500ETF","product_kind":"etf"}]
    data["revision"]="V1.4.1 / 中文方案名称与直接配置说明 / 2026-11-22"
    doc=data["doc100"]
    for k in ["reported_ds_score","score_status"]:doc["document"].pop(k,None)
    doc["document"]["content_score"]=dec["document_content_score"]
    doc["document"]["private_position_scope"]="文档所有人私人账户，不属于本用户；不纳入账户、目标、评分、证据或配置判断。"
    doc["fulltext"]=[b for b in doc["fulltext"] if not (241<=b["block"]<=273)]
    doc.get("calculations",{}).pop("account_arithmetic",None)
    doc["judgment"]={"current":"长期五基金为候选，国内四基金、留10%现金、开阳替代高鑫和增加科益为条件替代；60%/70%/40%现金方案为旧阶段提案，原八/七基金只作历史研究。",
                     "input_scope":"对话和文档只作参考输入；事实须由原始来源和日期独立核验。",
                     "private_scope":"私人账户全部排除，不属于用户。",
                     "content_score":76}
    for c in doc["claims"]:
        if c["id"]=="A25":
            c.update(status="excluded_unrelated_owner_account",topic="排除项",title="私人仓位已排除",
                     conclusion="文档持有人私人账户与本用户无关，不使用其中金额、仓位、交易或DOC确认状态。",
                     impact="不作为本用户账户事实、文档评分或组合配置依据。",source_ids=[])
        if c["id"]=="A26":
            c["conclusion"]="文档自身承认实验模型未校准；没有完整点时数据或预测战绩，不能用作市场胜率。关于私人职责文件与账户路由不纳入本用户研究。"
            c["impact"]="采纳可证伪与归档方法；个人仓位和内部DOC系统不继承。"
    for s in data["sources"]:
        if s["id"]=="D100":
            s["note"]="本次上传的市场、信用、AI和公司研究材料；引用须独立核验，私人账户排除。原件SHA256 "+doc["document"]["sha256"]
    section_map={s["id"]:s for s in soup.select("section.chapter")}
    # Existing interactions and raw datasets remain available in clearly historical appendices.
    legacy_doc=section_map["doc100"]
    lead=legacy_doc.select_one(".doc100-lead")
    if lead:lead.decompose()
    old_note=legacy_doc.select_one(".section-body>.note")
    if old_note:old_note.decompose()
    heading=legacy_doc.select_one(".section-head h2")
    heading.string="文档历史核验与假说索引"
    for p in legacy_doc.select("p"):
        text=p.get_text()
        if "DS 的 92" in text or "原 A 金额" in text:p.decompose()
        elif "另一些" in text:pass
    legacy_doc.find(id="doc100-downloads")
    for d in legacy_doc.select(".doc100-downloads"):
        for a in d.select("a[href='doc100/original.docx']"):a.decompose()
    # Owner-specific historical account sections and monetary references are not user evidence.
    for d in legacy_doc.select(".doc100-claim"):d.decompose()
    for p in legacy_doc.select("p"):
        if any(t in p.get_text() for t in ["43.56","43.3%","92 分","92分","92%","DOC00、DOC15"]):p.decompose()
    for tr in legacy_doc.select("tr"):
        if "43.56" in tr.get_text():
            cells=tr.select("td")
            if cells:cells[-1].string="个股草案属于文档所有人的研究，不作为本用户仓位或基金配置；私人账户信息排除。"
    for tr in section_map["audit"].select("tr"):
        if "方案二声称合计" in tr.get_text():tr.decompose()
    # Add transparent scope labels to every old chapter.
    for s in section_map.values():
        label=soup.new_tag("p",attrs={"class":"historical-label"})
        label.string="2026.11.21历史研究 · 原样本日期保留 · 不作为今日默认配置；当前结论见01—03"
        s.insert(0,label)
    core_ids=["market","blind","managers"]
    archive_ids=["verdict","audit","portfolio","scenarios","replay","execution","doc100"]
    core="".join(str(section_map[x]) for x in core_ids)
    archive="".join(str(section_map[x]) for x in archive_ids)
    doc_score_section="""<section class="chapter" id="document"><div class="section-head"><div class="section-index">07</div><div><span class="eyebrow">Reference quality / independent judgment</span><h2>文档按内容评价，对话按来源核验。</h2><p>两者都是研究输入，不拥有事实或当前配置的权威。文档所有人的私人账户已排除；不属于你的账户。</p></div></div><div class="section-body"><div class="doc100-review-quality"><span class="eyebrow">My content assessment / not a probability</span><h3 style="margin-top:14px">研究内容价值 <span id="content-score"></span></h3><p>仅评市场、信用、AI与公司研究内容，不计任何他人评分和私人仓位。人工评分不是可信概率、市场胜率或现金权重正确率；它只帮助说明材料在哪里有用、在哪里不能支持决策。</p><div class="table-scroll"><table><thead><tr><th>维度</th><th>评分</th><th>依据</th></tr></thead><tbody id="content-score-dimensions"></tbody></table></div></div><p>最有价值的增量，是财政融资不等于终端回报、技术成功不等于供应商利润、局部风险不能直接升级为系统危机。最弱的部分，是具体现金权重、买价与未来赔率没有统一的点时与替代比较。</p><details><summary>展开25组与市场相关的逐项核验</summary><div id="document-claim-summary"></div></details><p class="small">私人账户组保留“排除”状态只为审计追踪，不参与上述评分与配置。完整核验历史、10条假说和原件哈希在历史研究区，原文数值均按自己的日期使用。</p></div></section>"""
    daily_section="""<section class="chapter" id="daily"><div class="section-head"><div class="section-index">08</div><div><span class="eyebrow">Daily review / status before certainty</span><h2>每日状态与新增修正。</h2><p>北京时间08:20审视、09:20未成功补偿。证据采集、模型语义覆盖和独立事实确认分别记录，不把获取日期当作数据日期。</p></div></div><div class="section-body"><div class="status-surface" id="daily-review-status"><p>正在读取实际日审状态；未取得时不显示今日全面确认。</p></div><div id="daily-semantic-summary"></div><div class="hero-actions"><a class="current-download" href="daily/latest.json">最新证据状态 ↗</a><a class="current-download" href="daily/semantic-latest.json">最近成功的模型审议 ↗</a><a class="current-download" href="https://github.com/ARNEBEAR/fund-research/actions/workflows/daily-research.yml">执行记录 ↗</a></div><p class="small">模型免费接口尚未成功返回全量语义审议，网站明确展示失败；重要来源缺失不能靠模型补造。独立替代基金加入额外净值观察，工具费率、限额与溢价仍需专项核验。日审不连接账户、不下单。</p></div></section>"""
    daily_section=daily_section.replace('<div id="daily-semantic-summary"></div>','<p class="small">最近成功的模型结论显示于01顶部；本次人工配置基线仍按自己的日期使用，模型失败不推进结论日期。</p>')
    head=str(soup.head)
    head=head.replace("</style>",(ROOT/"report/asymmetry-current.css").read_text()+(ROOT/"report/asymmetry-decision.css").read_text()+(ROOT/"report/asymmetry-longterm.css").read_text()+"</style>",1)
    head=re.sub(r"<title>.*?</title>","<title>非对称 · 长期理想组合与同窗事实比较</title>",head)
    nav='''<nav class="nav-shell" aria-label="报告目录"><div class="wrap nav-inner"><a class="nav-brand" href="#top">非对称 ∿</a><a href="#current"><span class="num">01</span>长期候选</a><a href="#comparison"><span class="num">02</span>事实比较</a><a href="#possibilities"><span class="num">03</span>条件替代</a><a href="#independent"><span class="num">04</span>委托检验</a><a href="#market">市场</a><a href="#blind">净值</a><a href="#managers">经理</a><a href="#phase">阶段提案</a><a href="#daily">日审</a><a href="#history">历史</a><a href="#sources">来源</a></div><div class="reading-progress"></div></nav>'''
    hero='''<div class="wrap" id="top"><header class="masthead"><a class="brand" href="#top"><span class="brand-mark">∿</span>非对称 <span class="eyebrow">ASYMMETRY</span></a><div class="mast-meta"><span>HOLDER RESEARCH / V1.4</span><span>2026.11.22</span></div></header><div class="latest-hero"><div><span class="eyebrow">长期增长 / 回撤与修复一起检验</span><h1>让能力承担长期，<br>让证据约束信任。</h1><p>以权益长期增值为主，比较少数经理的委托价值。先看长期结构，再看同窗事实和条件替代；阶段性高现金不再默认等同长期目标。</p><div class="hero-actions"><a class="primary" href="#current" style="padding:12px 22px">查看长期候选 ↓</a><a class="current-download" href="#comparison">与旧方案事实比较 ↗</a></div></div><div class="hero-summary"><div><strong>L5</strong><p>长期五席候选 · 尚待验证</p></div><div><strong>230<span style="font-size:15px">万</span></strong><p>研究预算 · 非用户已核现仓</p></div><p class="small">约73.6%股权快照；承担权益损失，不承诺平滑或保本。D60保留为旧阶段风险提案。</p></div></div><div class="readmap"><a href="#current">长期结构</a><span>→</span><a href="#comparison">同窗事实</a><span>→</span><a href="#possibilities">条件替代</a><span>→</span><a href="#independent">继续验证</a></div></div>'''
    hero=hero.replace("HOLDER RESEARCH / V1.4","HOLDER RESEARCH / V1.4.1").replace("<strong>L5</strong>","<strong>五基金</strong>").replace("D60保留","60%现金方案保留")
    footer=str(soup.select_one("footer.footer"))
    oldscript=soup.select("#research-data + script")[0].string
    # Base chart/interactions still render retained archive elements. Do not seed status from old opinion scores.
    payload=json.dumps(data,ensure_ascii=False,separators=(",",":")).replace("</","<\\/")
    jsdoc=soup.select("script")[-1].string
    jsdoc=jsdoc.replace("DOC.claims.filter(c=>{","DOC.claims.filter(c=>{\n if(c.status==='excluded_unrelated_owner_account')return false;")
    helpers='<span id="filing-label" hidden></span><svg hidden aria-hidden="true"><g id="orbits"></g></svg>'
    stage_soup=BeautifulSoup((ROOT/"report/asymmetry-decision.html").read_text(),"html.parser")
    for old_id in ["current","possibilities","independent"]:
        stage_soup.find(id=old_id)["id"]="phase-"+old_id
    stage_soup.find(id="daily-semantic-summary").decompose()
    for node in stage_soup.find_all(string=True):
        if "当前首选" in node or "本期首选" in node or "本次独立研究首选" in node:
            node.replace_with(str(node).replace("本次独立研究首选","旧阶段研究提案").replace("当前首选","旧阶段提案").replace("本期首选","旧阶段提案"))
    stage_words={"D60":"60%现金方案","D70":"70%现金方案","R40":"40%现金方案","U60":"60%现金宽基方案"}
    for node in stage_soup.find_all(string=True):
        if any(k in node for k in stage_words):
            value=str(node)
            for k,v in stage_words.items():value=value.replace(k,v)
            node.replace_with(value)
    stage='<section class="chapter" id="phase"><div class="section-head"><div class="section-index">阶段</div><div><span class="eyebrow">Previous short-term proposals / dated assumptions</span><h2>旧阶段风险提案，保留边界与代价。</h2><p>D60/D70/R40/U60按约1—3个月问题提出，不能称为长期理想结构。市场风险并未因为目标澄清而消失；何时投入仍由买价、宏观、期限与损失能力决定。</p></div></div><div class="section-body"><details class="archive-fold"><summary>展开11月22日原D60/D70/R40及U60完整预算</summary><p class="phase-label">历史阶段提案 · 此处“当前”等文字只按当时假设理解；长期候选和事实比较见01—04。没有确认用户完整账户，也没有自动执行。</p>'+str(stage_soup)+'</details></div></section>'
    for k,v in stage_words.items():stage=stage.replace(k,v)
    output='<!doctype html><html lang="zh-CN">'+head+'<body>'+hero+nav+'<div class="wrap">'+(ROOT/"report/asymmetry-longterm.html").read_text()+core+stage+doc_score_section+daily_section+'<details id="history" class="archive-fold"><summary>历史研究与原A/B：仅供复盘，不作为今日默认配置</summary><p class="small">2026.11.21基线与旧输入审计，展开后可对照原假设、改变理由和方法代价。所有历史路径和情景均保留自己的日期。</p>'+archive+'</details>'+str(section_map["sources"])+footer+'</div>'+str(soup.select_one("#backtop"))+str(soup.select_one("#drawer-backdrop"))+str(soup.select_one("#source-drawer"))+helpers+'<script id="research-data" type="application/json">'+payload+'</script><script>'+oldscript+'</script><script>'+jsdoc+'</script><script>'+(ROOT/"report/asymmetry-decision.js").read_text()+'</script><script>'+(ROOT/"report/asymmetry-longterm.js").read_text()+'</script></body></html>'
    output=output.replace('本次人工配置基线仍按自己的日期使用','长期候选和旧阶段提案分别按自己的日期使用')
    (SITE/"index.html").write_text(output)
    (SITE/"research-data.json").write_text(json.dumps(data,ensure_ascii=False,indent=2))
    policy=SITE/"daily-policy";policy.mkdir(exist_ok=True)
    for n in ["decision-20261122-v13.json","macro-cash-20261122.md","independent-passive-20261122.json","longterm-comparison-20261122.json","longterm-research-20261122.md"]:
        shutil.copyfile(ROOT/"research"/n,policy/n)
    shutil.copyfile(ROOT/"research/asymmetry-daily-policy.json",policy/"policy.json")
    # Replace previous audit exports with the corrected input boundary; leave the uploaded source itself immutable.
    (SITE/"doc100/audit.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2))
    manifest=json.loads((SITE/"manifest.json").read_text())
    manifest.update(revision="V1.4.1",current_review_date="2026-11-22",current_preference="L5 long-term candidate; previous D60 only a dated short-term proposal",
                    doc100_private_account="excluded; unrelated to user",old_score="not used")
    for f in [SITE/"index.html",SITE/"research-data.json",SITE/"doc100/audit.json",*policy.iterdir()]:
        manifest["files"][str(f.relative_to(SITE))]={"bytes":f.stat().st_size,"sha256":sha(f.read_bytes())}
    (SITE/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print("Built V1.4.1 readable Chinese plan names and visible allocations; weights and calculations unchanged.")

if __name__=="__main__":main()
