(()=>{"use strict";
const D=window.REPORT_DATA, $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const p=(v,d=2)=>v==null?"—":`${v>=0?"+":""}${v.toFixed(d)}%`;
const val=v=>v==null?"—":v.toFixed(2)+"%";
const fund=c=>D.cards.find(x=>x.code===c);
const source=n=>D.sources.find(x=>x.number===n);
const cite=n=>`<a href="#s-${n}" data-source="${n}">[${n}]</a>`;
const svg=(w,h,body,label)=>`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}" xmlns="http://www.w3.org/2000/svg"><style>text{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif}</style>${body}</svg>`;
const text=(x,y,s,color="#b6b3ae",size=12,extra="")=>`<text x="${x}" y="${y}" fill="${color}" font-size="${size}" ${extra}>${esc(s)}</text>`;
$("weights").innerHTML=Object.entries(D.preferred.weights).map(([c,w])=>`<a class="weight" href="#fund-${c}" data-fund="${c}"><div class="number">${Math.round(w*100)}<small style="font-size:18px">%</small></div><h3>${esc(fund(c).name.replace("C",""))}</h3><p>${esc(fund(c).role)}<br>${esc(fund(c).managers.join(" / "))}</p></a>`).join("");
function compare(){
 const mode=$("comparison").value, cmp=D.comparisons[mode], n=$("window").value, daily=$("rebalance").value==="daily";
 const rows=Object.entries(cmp.portfolios), metrics=k=>(daily?cmp.portfolios[k].daily_rebalanced:cmp.portfolios[k].metrics)[n];
 $("comparison-note").textContent=`共同全样本：${cmp.start}—${cmp.end}。${daily?"每日恢复原权重":"每个展示窗口期初按原比例配置后不再平衡"}。${mode==="global"?"全球短样本不具备2026年初端点，年初至今留空。":"所有方案使用同一共同净值日期网格。"}`;
 $("portfolio-rows").innerHTML=rows.map(([k,r])=>{let m=metrics(k);return `<tr><td class="${k==="J"?"primary":""}">${esc(r.name)}${k==="J"?" · 首选":""}</td><td class="${m&&m.return_pct>=0?"positive":"negative"}">${p(m?.return_pct)}</td><td>${p(m?.mdd_pct)}</td><td>${val(m?.vol_pct)}</td><td>${val(r.q3_equity_pct)}</td></tr>`}).join("");
 const available=rows.filter(([k])=>metrics(k));let b="";
 if(!available.length){$("portfolio-chart").innerHTML="<p>此共同样本没有年初端点，请切换120日或全样本。</p>";}
 else{
 const lo=Math.min(0,...available.map(([k])=>metrics(k).return_pct))-2,hi=Math.max(0,...available.map(([k])=>metrics(k).return_pct))+2;
 const x=v=>255+(v-lo)/(hi-lo)*660,h=80+rows.length*48;
 b+=text(18,24,"收益比较 · 同额、同起止", "#eeeae3",14);
 b+=`<line x1="${x(0)}" y1="45" x2="${x(0)}" y2="${h-30}" stroke="#55534f"/>`;
 for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4;b+=text(x(v),h-9,v.toFixed(1)+"%","#8a8c90",11,'text-anchor="middle"');}
 rows.forEach(([k,r],i)=>{const m=metrics(k),y=58+i*48; b+=text(18,y+16,r.name,k==="J"?"#dfc39b":"#d0ccc5",13);
 if(m){b+=`<rect x="${Math.min(x(0),x(m.return_pct))}" y="${y}" width="${Math.max(1,Math.abs(x(m.return_pct)-x(0)))}" height="23" rx="3" fill="${k==="J"?"#dfc39b":m.return_pct>=0?"#7da58f":"#9a696e"}"><title>${esc(r.name)}：收益${p(m.return_pct)}，最大回撤${p(m.mdd_pct)}</title></rect>`;b+=text(965,y+17,p(m.return_pct),k==="J"?"#dfc39b":"#bab7b0",12,'text-anchor="end"');}});
 $("portfolio-chart").innerHTML=svg(1000,h,b,"各方案收益比较");
 }
 const r=cmp.portfolios.J, rc=r.risk_contributions120, risk=(rc["021180"]+(rc["012817"]||0))*100;
 $("risk-note").innerHTML=`<b>风险仍集中，不能承诺小回撤。</b> 首选中产业15%＋致和10%，在共同120区间协方差分解中仍贡献约${risk.toFixed(1)}%方差；三季快照穿透股票约${r.q3_equity_pct.toFixed(1)}%。风险贡献来自恢复原权重的历史协方差，不是未来损失占比。<br>首选未胜过所有方案：开阳替代、质量防守、三只精简各有优势；新增质量席位也没有把最近60区间变成盈利。`;
}
["comparison","window","rebalance"].forEach(id=>$(id).addEventListener("change",compare));compare();
for(const g of Object.keys(D.groups))$("group").insertAdjacentHTML("beforeend",`<option value="${esc(g)}">${esc(g)}</option>`);
const axes=["角色清晰","跨期执行","风险纪律","纠错进化","解释可核查"];
function cardHTML(c){
 const qs=c.quarters.filter(q=>q.excerpt), cites=c.quarters.map(q=>cite(q.source)).join(" ");
 const peer=c.peer_windows.map(x=>`<tr><td>${x.window==="YTD"?"2026年至今":x.window+"区间"}</td><td>${p(x.return_pct)}</td><td>${p(x.mdd_pct)}</td><td>${x.rank}/${x.count}</td><td>${x.start}—${x.end}</td></tr>`).join("");
 return `<details class="fund" id="fund-${c.code}"><summary><div class="summary-main"><span class="verdict ${c.verdict==="好"?"good":"bad"}">${c.verdict}</span><span class="tag">${esc(c.action)}</span><h3>${esc(c.name)}</h3><div class="identity">${c.code} / ${esc(c.managers.join("、"))} / ${esc(c.role)}</div></div><div class="scores"><span>履职<b>${c.score}</b></span><span>同类<b>${c.peer}</b></span><span>席位<b>${c.seat}</b></span></div></summary>
 <div class="fund-content"><p class="thesis">${esc(c.thesis)}</p><p class="fund-foot">结论置信度：${esc(c.confidence)} · 履职五项等权平均 · 三轴人工分数，不是全市场百分位 · “坏”指当前不值得配置</p>
 <div class="axis-bars">${axes.map((a,i)=>`<div><span>${a}</span><b>${c.axes[i]}</b><div class="axis-track"><i style="width:${c.axes[i]}%"></i></div></div>`).join("")}</div>
 <div class="lenses"><article class="lens"><h4>披露事实与跨期推理</h4><p>${esc(c.trajectory)} ${cites}</p></article><article class="lens"><h4>值得相信的地方</h4><p>${esc(c.strength)}</p></article><article class="lens"><h4>不愿替它掩饰的问题</h4><p>${esc(c.weakness)}</p></article><article class="lens"><h4>放进整个组合以后</h4><p>${esc(c.synergy)}</p></article><article class="lens"><h4>是否有更佳备选</h4><p>${esc(c.alternative)}</p></article><article class="lens"><h4>披露后的行为观察</h4><p>${c.post_disclosure?`${c.post_disclosure.start}—${c.post_disclosure.end}，正式净值收益${p(c.post_disclosure.return_pct)}，区间最大回撤${p(c.post_disclosure.mdd_pct)}。`:"共同净值尚不足。"}从发布日期当日或之后首个净值作锚，下一收益区间才算观察。此短段用于挑战观点，不认证调仓时点或因果。</p></article></div>
 <p class="falsifier"><b>什么会让我改判</b>　${esc(c.falsifier)}</p>
 <details class="source-detail"><summary>同角色候选、共同风险与原文轨迹</summary>
 <p class="micro">角色组：${esc(c.group)}（${D.groups[c.group].length}只）；收益排名仅在该列表内部。经理共管、新任与份额成立限制按正文解释。排名不等于全市场同类Top；更长窗口缺失留空。</p>
 <div class="table-wrap"><table><thead><tr><th>窗口</th><th>收益</th><th>最大回撤</th><th>组内收益位次</th><th>共同端点</th></tr></thead><tbody>${peer}</tbody></table></div>
 <p class="micro">原生日收益共同120区间中联动较高：${c.nearest_correlated.map(x=>`${esc(x.name)} ${x.corr.toFixed(2)}`).join("；")}。高相关不证明完整持仓相同，低相关不保证危机保护。</p>
 <p class="micro">最新正式净值 ${c.nav_date} / ${c.nav.toFixed(4)}；三季股票占净资产${c.q3_equity_pct.toFixed(2)}%。</p>
 ${qs.map(q=>`<div class="quarter"><b>${q.quarter==="H1"?"2026中报":"2026 Q"+q.quarter}</b> · 持仓${q.holdings_asof} · 发布${q.published_on} ${cite(q.source)}<pre>${esc(q.excerpt)}</pre></div>`).join("")}
 ${c.long_sources.length?`<p class="micro">更早公开观点 / 管理人变更：${c.long_sources.map(cite).join(" ")}</p>`:"<p class='micro'>没有为这位经理补造更早的直接访谈；跨期判断以已列披露为主。</p>"}
 </details></div></details>`;
}
function openFund(code){
 $("search").value="";$("group").value="";$("verdict").value="";renderCards();
 const el=$("fund-"+code);if(el){el.open=true;history.replaceState(null,"","#fund-"+code);el.scrollIntoView({behavior:"smooth",block:"start"});}
}
function renderCards(){
 const query=$("search").value.trim().toLowerCase(),group=$("group").value,v=$("verdict").value,sort=$("sort").value;
 let cs=D.cards.filter(c=>(!query||[c.name,c.code,c.managers.join(" ")].join(" ").toLowerCase().includes(query))&&(!group||c.group===group)&&(!v||(v==="selected"?c.code in D.preferred.weights:c.verdict===v)));
 if(sort!=="original")cs.sort((a,b)=>b[sort]-a[sort]);
 $("count").textContent=`${cs.length} / ${D.cards.length}只`;
 $("cards").innerHTML=cs.map(cardHTML).join("");$("empty").hidden=!!cs.length;
 const h=70+cs.length*32;let b=text(20,22,"履职","#dfc39b",12)+text(85,22,"同类","#91b8e5",12)+text(150,22,"席位","#98d9bb",12);
 [50,65,80,100].forEach(v=>{let x=260+v*6;b+=`<line x1="${x}" y1="43" x2="${x}" y2="${h-21}" stroke="#2a2c30"/>`+text(x,h-3,String(v),"#888b91",10,'text-anchor="middle"');});
 cs.forEach((c,i)=>{let y=55+i*32;b+=text(18,y+5,c.name.replace("C",""),c.verdict==="坏"?"#b38789":"#c9c5bf",12,`class="clickable" data-open="${c.code}" tabindex="0" role="button"`);[[c.score,"#dfc39b",-4],[c.peer,"#91b8e5",0],[c.seat,"#98d9bb",4]].forEach(([v,col,dy])=>{b+=`<circle cx="${260+v*6}" cy="${y+dy}" r="4" fill="${col}"><title>${esc(c.name)}：${v}分</title></circle>`});});
 $("score-chart").innerHTML=svg(910,h,b,"31只候选三轴判断分数");
}
["search","group","verdict","sort"].forEach(id=>$(id).addEventListener(id==="search"?"input":"change",renderCards));renderCards();
let codes=D.correlations.codes,W=1050,cell=65,offset=255;let b=text(18,22,"日收益共同联动 · 120区间","#eeeae3",14);
codes.forEach((c,i)=>{b+=text(offset+i*cell+cell/2,47,fund(c).name.slice(0,4),"#aaa9a6",11,'text-anchor="middle"');b+=text(18,78+i*cell,fund(c).name.replace("C",""),"#c9c5bf",12);
 codes.forEach((cc,j)=>{let r=D.correlations.matrix[i][j],alpha=Math.abs(r)*.67+.10;const color=r>=0?`rgba(190,148,110,${alpha})`:`rgba(102,150,186,${alpha})`;b+=`<rect x="${offset+j*cell}" y="${54+i*cell}" width="${cell-4}" height="${cell-4}" rx="4" fill="${color}"><title>${esc(fund(c).name)} / ${esc(fund(cc).name)}：${r.toFixed(2)}</title></rect>`+text(offset+j*cell+(cell-4)/2,90+i*cell,r.toFixed(2),"#eeeae3",12,'text-anchor="middle"');});
});
$("heatmap").innerHTML=svg(W,72+codes.length*cell,b,"成长、全球与价值基金日收益相关矩阵");
$("correlation-note").textContent=`${D.correlations.start}—${D.correlations.end}，31只原生日收益共同对齐后最近120区间。图仅展示10只，使用同一个矩阵端点。相关系数描述历史共振，不是风险上限，也不能据此还原当下持仓。`;
$("quality").textContent=`本轮重新采集31只正式净值；同一数据商JS与历史净值接口交叉核对620个点，发现差异0。保留${D.data_quality.quarter_sources}份季度/中报证据及${D.sources.length}条来源。两接口属同一数据商，不算独立双源；全历史未逐点独立核验。修正旧数据商部分零收益与净值冲突，过程与CSV在复算包中。`;
$("nav-dates").innerHTML=`<table><thead><tr><th>基金</th><th>代码</th><th>正式净值日</th><th>单位净值</th></tr></thead><tbody>${D.cards.map(c=>`<tr><td>${esc(c.name)}</td><td>${c.code}</td><td>${c.nav_date}</td><td>${c.nav.toFixed(4)}</td></tr>`).join("")}</tbody></table>`;
$("sources").innerHTML=D.sources.map(s=>`<li id="s-${s.number}"><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a> · ${esc(s.published_on||s.date||"日期见标题/原文")}${s.holdings_asof?" · 快照"+s.holdings_asof:""}${s.pages.length?" · PDF页"+s.pages.join("、"):""}${s.extract?` · <a href="${esc(s.extract)}" download>摘录</a>`:""}${s.sha256?`<span class="source-hash">来源文件 SHA-256 ${esc(s.sha256)}</span>`:""}</li>`).join("");
document.addEventListener("click",e=>{
 const a=e.target.closest("[data-source]");if(a){e.preventDefault();$("evidence").querySelector("details").open=true;const el=$("s-"+a.dataset.source);history.replaceState(null,"","#s-"+a.dataset.source);el.scrollIntoView({behavior:"smooth"});}
 const f=e.target.closest("[data-fund],[data-open]");if(f){e.preventDefault();openFund(f.dataset.fund||f.dataset.open);}
});
document.addEventListener("keydown",e=>{if((e.key==="Enter"||e.key===" ")&&e.target.dataset.open){e.preventDefault();openFund(e.target.dataset.open);}});
if(location.hash.startsWith("#fund-"))openFund(location.hash.slice(6));
if(location.hash.startsWith("#s-")){$("evidence").querySelector("details").open=true;$(location.hash.slice(1))?.scrollIntoView();}
window.JUDGMENT_READY=true;
})();
