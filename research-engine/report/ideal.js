"use strict";
const D=PACK.analysis,N=PACK.notes,$=id=>document.getElementById(id);
const num=(v,n=1)=>Number(v).toFixed(n),pct=(v,n=1)=>(v>0?"+":"")+num(v*100,n)+"%",plain=(v,n=1)=>num(v*100,n)+"%",wan=(v,n=1)=>num(v/10000,n)+"万";
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const codes=D.policy.positions.map(p=>p.code),positions=Object.fromEntries(D.policy.positions.map(p=>[p.code,p]));
const short={"022714":"万家蓝筹","021180":"产业机遇","010390":"科益","011370":"华商均衡","519697":"交银优势","022415":"前海国企","021902":"广发主题","006075":"标普代理","027170":"交银环球","002611":"黄金代理"};
const labels={target:"截图目标",no_gold:"无黄金", "gold_6%":"黄金6%","gold_20%":"黄金20%",eight_role_merge:"8项变体",old_reported_scaled:"9月17日旧口径"};
const charts={};
const axis={axisLine:{lineStyle:{color:"#33434b"}},axisTick:{show:false},axisLabel:{color:"#a0b1b6",fontSize:10},splitLine:{lineStyle:{color:"#27343b",type:"dashed"}}};
const tooltip={trigger:"axis",confine:true,backgroundColor:"#18232b",borderColor:"#47605b",textStyle:{color:"#e8eeeb",fontSize:12}};
function chart(id,option){const c=charts[id]||(charts[id]=echarts.init($(id),null,{width:$(id).clientWidth||600,height:$(id).clientHeight||330}));c.setOption({animation:false,backgroundColor:"transparent",...option},true);}
const target=D.weekly.results.find(r=>r.id==="target"),latest=Object.fromEntries(D.latest.map(r=>[r.code,r]));
$("dates").textContent=`境内与黄金净值至${D.latest_event.end} · QDII至${latest["006075"].date} · 完整周截止${D.weekly.cutoff} · 全组合共同日频至${D.daily.end}`;
$("kpis").innerHTML=[["目标金额","246.80万","10项配置，未记为实际持仓"],["普通年化波动",plain(target.vol,2),`共同${D.weekly.n}周，非未来波动预测`],["日频最大回撤",pct(D.daily.mdd,2),"共同日、每日恢复权重，非损失上限"],["黄金目标",plain(D.groups.gold,2),"不同资产来源，不是稳定保险"]].map(([a,b,c])=>`<div class="kpi"><small>${a}</small><strong>${b}</strong><p>${c}</p></div>`).join("");
$("changes").innerHTML=N.changes.map(r=>`<article class="finding"><h3>${esc(r.title)}</h3><p>${esc(r.text)}</p></article>`).join("");
$("current-judgment").textContent=N.current_judgment;
const currentEvent=D.latest_event;
$("event-note").textContent=`${currentEvent.start}—${currentEvent.end}。覆盖目标${wan(currentEvent.covered_cny,2)} / 246.80万（${plain(currentEvent.coverage)}），已覆盖部分${pct(currentEvent.covered_return,2)}，静态映射${wan(currentEvent.change_cny,2)}。${currentEvent.missing_codes.length?"缺失同日QDII不填0，不计算完整组合当日收益。":"同日净值已全覆盖，仍为目标金额映射而非账户盈亏。"}`;
$("weekly-note").textContent=`完整周截至${D.weekly.cutoff}；晚于该日的境内行情单列，不混入完整周。全组合共同日频终点${D.daily.end}。`;
$("followup-note").textContent=D.previous_review?.followup?`${D.previous_review.date}冻结目标的前瞻跟踪：${D.previous_review.followup.start}—${D.previous_review.followup.end}，${pct(D.previous_review.followup.return,2)}；短样本不是验证成功。`:"上期研究之后，尚无足够共同净值形成前瞻跟踪；逐只新增净值不能算作建议发布后的预测成绩。";
chart("event-chart",{tooltip,grid:{left:72,right:30,top:14,bottom:33},xAxis:{...axis,type:"value",axisLabel:{...axis.axisLabel,formatter:v=>v+"%"}},yAxis:{...axis,type:"category",inverse:true,data:Object.keys(currentEvent.fund_returns).map(c=>short[c]),splitLine:{show:false}},
 series:[{name:"区间涨跌",type:"bar",barMaxWidth:21,label:{show:true,position:"right",color:"#c8d8d3",fontSize:10,formatter:p=>num(p.value,2)+"%"},data:Object.values(currentEvent.fund_returns).map(v=>({value:v*100,itemStyle:{color:v>=0?"#99dec5":"#bd919c"}}))}]});
$("target-rows").innerHTML=D.policy.positions.map(p=>{const a=N.actions[p.code],f=a.forward_response;return`<tr><td><strong>${esc(p.name)}</strong><br><span class="micro">${p.code}${p.proxy?" · 测算代理":""} / ${esc(p.role)}</span></td><td class="amount">${wan(p.amount_cny,2)}<br>${plain(p.amount_cny/D.policy.total_cny,2)}</td><td>${latest[p.code].date}<br>近20日 ${pct(latest[p.code].return20,1)}</td><td><strong style="color:var(--green)">${esc(a.action)}</strong>${f?`<p class="micro">未来条件模型：修复 ${pct(f.repair)} / 股金同跌 ${pct(f.rates_stress)}；非预测。</p>`:""}<br>${esc(a.reason)}${p.note?`<br><span class="micro">${esc(p.note)}</span>`:""}</td></tr>`;}).join("");
chart("risk-chart",{tooltip,legend:{top:0,textStyle:{color:"#aabbb5",fontSize:10}},grid:{left:75,right:25,top:50,bottom:35},
 xAxis:{...axis,type:"value",axisLabel:{...axis.axisLabel,formatter:v=>v+"%"}},yAxis:{...axis,type:"category",inverse:true,data:codes.map(c=>short[c]),splitLine:{show:false}},
 series:[{name:"金额权重",type:"bar",barMaxWidth:12,itemStyle:{color:"#83aee4"},data:codes.map(c=>positions[c].amount_cny/D.policy.total_cny*100)},{name:"普通方差贡献",type:"bar",barMaxWidth:12,itemStyle:{color:"#98e1c3"},data:codes.map(c=>D.weekly.risk_contributions[c]*100)}]});
const tech=["022714","021180","010390","011370"],sat=["010390","011370"];
$("risk-note").textContent=`国内四只成长/科技占金额${plain(D.groups.domestic_technology)}，共同周方差贡献${plain(tech.reduce((s,c)=>s+D.weekly.risk_contributions[c],0))}；科益＋华商贡献${plain(sat.reduce((s,c)=>s+D.weekly.risk_contributions[c],0))}。贡献可为负，不等于永久对冲，也不是未来损失比例。`;
const paths=D.weekly.paths;
chart("path-chart",{tooltip,legend:{top:0,textStyle:{color:"#aabbb5",fontSize:10}},grid:{left:44,right:15,top:63,bottom:38},
 xAxis:{...axis,type:"category",data:paths.dates,axisLabel:{...axis.axisLabel,formatter:v=>v.slice(5)}},yAxis:{...axis,type:"value",axisLabel:{...axis.axisLabel,formatter:v=>v+"%"}},
 series:["target","no_gold","old_reported_scaled"].map((key,i)=>({name:labels[key],type:"line",showSymbol:false,lineStyle:{width:2,color:["#98e1c3","#eac68d","#829ebf"][i]},itemStyle:{color:["#98e1c3","#eac68d","#829ebf"][i]},data:paths.values[key].map(v=>(v-1)*100)}))});
$("path-note").textContent=`${D.weekly.start}—${D.weekly.cutoff}，共同${D.weekly.n}周，固定目标每周再平衡。旧口径按比例放大到246.80万，只用于同额参照，不能解释今年实际账户收益。`;
$("sensitivity").textContent=`日频${D.daily.start}—${D.daily.end}：波动${plain(D.daily.vol,2)}、回撤${pct(D.daily.mdd,2)}。期初持有不再平衡：周波动${plain(D.buyhold.vol,2)}、回撤${pct(D.buyhold.mdd,2)}。交银环球单列A类、限制新团队后${D.a_sensitivity.n}周：波动${plain(D.a_sensitivity.vol,2)}、回撤${pct(D.a_sensitivity.mdd,2)}。黄金更换华安C代理的组合波动${plain(D.gold_proxy_sensitivity.vol,2)}；A/C历史不拼接。`;
const pairNotes={"010390/011370":"子行业不同仍有共同科技风险","006075/027170":"海外主动仓需证明额外价值","519697/022714":"轮动仓不保证隔离成长","519697/021902":"两种仓位管理方法存在差异","002611/006075":"黄金与美股可能同跌","002611/011370":"黄金不是固定科技对冲","022415/021902":"价值和平衡仓也存在共同风险"};
$("pairs").innerHTML=D.interactions.map(r=>`<tr><td>${short[r.a]} / ${short[r.b]}</td><td>${num(r.correlation,3)} · ${r.n}周</td><td>${pairNotes[r.a+"/"+r.b]}</td></tr>`).join("");
function renderGold(){const r=D.gold_evidence.find(r=>r.window===Number($("gold-window").value));const up=Math.round(r.gold_positive_when_tech_down*r.technology_down_weeks);
 chart("gold-chart",{tooltip:{...tooltip,trigger:"item",formatter:"{b}：{c}周"},series:[{type:"pie",radius:["40%","65%"],center:["50%","47%"],label:{color:"#c3d2ce",fontSize:11,formatter:"{b}\n{c}周"},data:[{name:"黄金上涨",value:up,itemStyle:{color:"#98e1c3"}},{name:"黄金未上涨",value:r.technology_down_weeks-up,itemStyle:{color:"#bd919c"}}]}]});
 $("gold-note").textContent=`最近${r.window}周，黄金与等权科技相关${num(r.correlation_tech,3)}；科技下跌的${r.technology_down_weeks}周中，黄金同跌${r.both_down_weeks}周，黄金平均收益${pct(r.gold_mean_when_tech_down,2)}。普通同日历周，重叠窗口非独立证据。`;
}
function renderPlans(){const key=$("plan-metric").value,rows=D.weekly.results.filter(r=>r.id!=="old_reported_scaled");
 chart("plans-chart",{tooltip,grid:{left:85,right:30,top:10,bottom:38},xAxis:{...axis,type:"value",axisLabel:{...axis.axisLabel,formatter:v=>v+"%"}},yAxis:{...axis,type:"category",inverse:true,data:rows.map(r=>labels[r.id]),splitLine:{show:false}},
 series:[{name:$("plan-metric").selectedOptions[0].textContent,type:"bar",barMaxWidth:25,label:{show:true,position:"right",fontSize:10,color:"#d0dfda",formatter:p=>num(p.value,2)+"%"},data:rows.map(r=>({value:r[key]*100,itemStyle:{color:r.id==="target"?"#98e1c3":"#899ead"}}))}]});
}
$("plan-rows").innerHTML=D.weekly.results.map(r=>`<tr><td>${labels[r.id]}</td><td>${plain(r.vol,2)}</td><td>${pct(r.mdd,2)}</td><td>${pct(r.return,2)}</td></tr>`).join("");
const ci=D.weekly.results.find(r=>r.id==="no_gold").vol_delta_vs_target_ci90;
$("gold-ci").textContent=`无黄金相对目标的普通波动差，4周共同块重采样90%区间[${num(ci[0]*100,2)}, ${num(ci[1]*100,2)}]个百分点，跨0；不能据此证明12.24%最优或黄金无效。`;
function renderScenario(){const id=$("scenario-plan").value,rows=D.scenarios.map(s=>s.plans[id]),names=D.scenarios.map(s=>s.name);
 chart("scenario-chart",{tooltip:{...tooltip,formatter:p=>{const r=rows[p[0].dataIndex];return `${esc(names[p[0].dataIndex])}<br>${wan(r.min_cny,2)} ～ ${wan(r.max_cny,2)}<br>窗口范围，非概率区间`;}},
 grid:{left:window.innerWidth<600?100:172,right:55,top:15,bottom:35},xAxis:{...axis,type:"value",name:"万元",nameTextStyle:{color:"#91a7ae"},axisLabel:{...axis.axisLabel}},yAxis:{...axis,type:"category",inverse:true,data:window.innerWidth<600?["震荡分化","科技修复","增长担忧","股金同跌"]:names,splitLine:{show:false}},
 series:[{name:"条件响应范围",type:"custom",encode:{x:[0,1],y:2},renderItem:(params,api)=>{const start=api.coord([api.value(0),api.value(2)]),end=api.coord([api.value(1),api.value(2)]),positive=api.value(0)>=0,color=positive?"#98e1c3":"#bd919c";return{type:"group",children:[{type:"line",shape:{x1:start[0],y1:start[1],x2:end[0],y2:end[1]},style:{stroke:color,lineWidth:8}},{type:"circle",shape:{cx:start[0],cy:start[1],r:4},style:{fill:color}},{type:"circle",shape:{cx:end[0],cy:end[1],r:4},style:{fill:color}}]};},data:rows.map((r,i)=>[r.min_cny/10000,r.max_cny/10000,i])}]});
 $("scenario-rows").innerHTML=D.scenarios.map(s=>{const r=s.plans[id];return`<tr><td>${esc(s.name)}</td><td>${["market","communication","dividend","sp500","gold"].map(k=>pct(s[k],0)).join(" / ")}</td><td>${pct(r.min)} ～ ${pct(r.max)}</td><td>${wan(r.min_cny,1)} ～ ${wan(r.max_cny,1)}</td></tr>`;}).join("");
}
$("outlook-cards").innerHTML=N.outlook.map(r=>`<article class="future-card"><h3>${esc(r.title)}</h3><p>${esc(r.text)}</p></article>`).join("");
$("sources").innerHTML=PACK.sources.map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)} ↗</a>`).join("");
$("gold-window").addEventListener("change",renderGold);$("plan-metric").addEventListener("change",renderPlans);$("scenario-plan").addEventListener("change",renderScenario);
$("print").addEventListener("click",()=>window.print());
document.querySelectorAll("[data-save]").forEach(b=>b.addEventListener("click",()=>{const a=document.createElement("a");a.href=charts[b.dataset.save].getDataURL({type:"png",pixelRatio:2,backgroundColor:"#101418"});a.download=`portfolio-${D.date}-${b.dataset.save}.png`;a.click();}));
let resize;window.addEventListener("resize",()=>{clearTimeout(resize);resize=setTimeout(()=>{Object.values(charts).forEach(c=>c.resize());renderScenario();},150);});
renderGold();renderPlans();renderScenario();
function renderForward(){
 const F=PACK.forward,I=PACK.intelligence;if(!F)return;
 const t=F.robust.find(r=>r.id==="target");
 $("forward-kpis").innerHTML=[["假设集内20日期望响应",`${pct(t.mean_range[0])} ～ ${pct(t.mean_range[1])}`,"人工权重不确定性范围"],["条件盈亏比",`${num(t.gain_loss_ratio_range[0],2)} ～ ${num(t.gain_loss_ratio_range[1],2)}`,"不是实际市场赔率"],["修复至少需要多大权重",F.breakeven_bull_vs_bear==null?"—":plain(F.breakeven_bull_vs_bear),"仅修复/增长担忧两分支盈亏平衡"]].map(([a,b,c])=>`<div class="kpi"><small>${a}</small><strong>${b}</strong><p>${c}</p></div>`).join("");
 $("event-calendar").innerHTML=F.events.map(e=>`<article class="event-card"><time>${esc(e.date)} 北京时间</time><h3><a href="${esc(e.source)}" target="_blank" rel="noopener noreferrer">${esc(e.name)} ↗</a></h3><p>兑现：${esc(e.positive)}</p><p>落空：${esc(e.negative)}</p></article>`).join("")||'<p class="notice">暂无足够已核实的近期日历事件，保留条件分支，不编造催化日期。</p>';
 $("robust-rows").innerHTML=F.robust.map(r=>`<tr><td>${labels[r.id]}</td><td>${pct(r.mean_range[0])} ～ ${pct(r.mean_range[1])}</td><td>${num(r.gain_loss_ratio_range[0],2)} ～ ${num(r.gain_loss_ratio_range[1],2)}</td></tr>`).join("");
 $("breakeven-note").textContent=F.breakeven_bull_vs_bear==null?"当前分支响应不满足一正一负，无法计算两分支盈亏平衡点。":`只在修复/增长担忧两分支之间比较，需要修复权重至少约${plain(F.breakeven_bull_vs_bear)}才能盈亏平衡。这是需要达到的判断门槛，不是我们已经掌握的上涨概率。`;
 $("tail-rows").innerHTML=F.branches.map(b=>{const r=b.responses.target;return`<tr><td>${esc(b.name)}</td><td>${plain(b.weight_bounds[0],0)}～${plain(b.weight_bounds[1],0)}</td><td>${pct(r.q10)} / ${pct(r.q90)}</td><td>${wan(r.expected_shortfall10*D.policy.total_cny,1)}</td></tr>`;}).join("");
 $("forward-method").innerHTML=[F.weight_rule,...F.limits,F.calibration.note,`共同估计样本${F.estimation.start}—${F.estimation.end}，${F.estimation.n}个日频点；${F.simulations_per_branch}条路径/分支。`].map(s=>`<p>${esc(s)}</p>`).join("");
 const failed=I.sources.filter(s=>s.status!=="ok").map(s=>s.name||s.id);
 $("intel-coverage").textContent=`${I.collected_at.slice(0,16).replace("T"," ")}采集 · ${I.coverage.ok}/${I.coverage.total}路成功${failed.length?" · 缺失："+failed.join("、"):""}。标题与发行人自述不直接转换成上涨概率。`;
 const display=I.items.slice(0,8);
 $("intel-items").innerHTML=display.map(item=>{
   let impact=item.topic==="rates"?"影响利率与股金共跌分支；发布日期与生效日分开。":item.topic==="manager"?"影响产品可买性、经理职责或仓位假设；需对照披露后的真实行为。":"影响盈利兑现分支；公司陈述不等于独立审计结论。";
   if(item.metrics?.operating_cashflow_ytd_cny<0)impact=`原文经营现金流年初至今${wan(item.metrics.operating_cashflow_ytd_cny,0)}。即使利润增长，也要复核现金回收与营运资金，不能只取利好。`;
   return `<article class="evidence-item"><span class="micro">${esc(item.published_on)} · ${esc(item.status)}</span><p><a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">${esc(item.title)} ↗</a></p><p>${esc(impact)}</p>${item.excerpt?`<details><summary>原文片段 / 已核解读</summary><p>${esc(item.excerpt)}</p></details>`:""}</article>`;
 }).join("");
 renderForwardPath();
}
function renderForwardPath(){const F=PACK.forward;if(!F)return;const branch=$("forward-branch").value,fan=F.path_fans[branch],b=F.branches.find(r=>r.id===branch);
 chart("forward-chart",{tooltip,legend:{top:0,textStyle:{color:"#aabbb5",fontSize:10}},grid:{left:44,right:18,top:55,bottom:40},xAxis:{...axis,type:"category",data:F.path_days,axisLabel:{...axis.axisLabel,formatter:v=>v.slice(5)}},yAxis:{...axis,type:"value",axisLabel:{...axis.axisLabel,formatter:v=>v+"%"}},
 series:[["p10","10分位","#bd919c"],["median","中位路径","#98e1c3"],["p90","90分位","#83aee4"]].map(([key,name,color])=>({name,type:"line",showSymbol:false,lineStyle:{color,width:key==="median"?2.5:1.2,type:key==="median"?"solid":"dashed"},itemStyle:{color},data:fan[key].map(v=>v*100),...(key==="median"?{markLine:{symbol:"none",label:{fontSize:9,color:"#eac68d",formatter:"事件"},lineStyle:{color:"#eac68d",type:"dotted"},data:F.event_indexes.map(i=>({xAxis:F.path_days[i]}))}}:{})}))});
 $("forward-path-note").textContent=`${b.name}：20日收益中位数${pct(b.responses.target.median)}，10/90分位${pct(b.responses.target.q10)} / ${pct(b.responses.target.q90)}。分位数来自条件扰动路径，不是未来置信区间；工作日近似不完全对应基金交易日。`;
}
$("forward-branch").addEventListener("change",renderForwardPath);
document.querySelectorAll("details").forEach(d=>d.addEventListener("toggle",()=>{if(d.open)requestAnimationFrame(()=>Object.values(charts).forEach(c=>c.resize()));}));
renderForward();
fetch("../../reports/index.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("registry");return r.json();}).then(rows=>{
 const select=$("date-picker");select.innerHTML=rows.filter(r=>/^\d{4}-\d{2}-\d{2}$/.test(r.date)).map(r=>`<option value="${r.date}" ${r.date===D.date?"selected":""}>${r.date}${r===rows[0]?" · 最新":""}</option>`).join("");
 select.addEventListener("change",()=>{const row=rows.find(r=>r.date===select.value);if(row&&/^reports\/\d{4}-\d{2}-\d{2}\/$/.test(row.path))location.href="../../"+row.path;});
 window.DATE_PICKER_READY=true;
}).catch(()=>{$("date-picker").setAttribute("aria-label","日期列表暂不可用，可打开档案");window.DATE_PICKER_READY=false;});
fetch("../../automation-status.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("status");return r.json();}).then(s=>{
 const stale=s.last_success&&(Date.now()-Date.parse(s.last_success+"T00:00:00+08:00"))>48*3600000;
 $("automation-state").textContent=s.state==="failed_keep_previous"?"本轮失败 · 保留上次成功 "+s.last_success:stale?"更新延迟 · 最新成功 "+s.last_success:"每日08:20 · 最新成功 "+(s.last_success||D.date);
}).catch(()=>{$("automation-state").textContent="每日规则研究 · 查看档案日期";});
window.PORTFOLIO_READY=true;
