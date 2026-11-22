(function(){
'use strict';
const D=window.MARKET_REVIEW,$=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=(v,d=2)=>Number.isFinite(v)?(v>=0?'+':'')+(v*100).toFixed(d)+'%':'—';
const pp=v=>Number.isFinite(v)?(v>=0?'+':'')+(v*100).toFixed(2):'—';
const plain=v=>Number.isFinite(v)?v.toFixed(2)+'%':'—';
const fmtDate=s=>s||'未取得';
let period='3Y',selected=['007466','006624','007343'],showBase=false;
const style=getComputedStyle(document.documentElement),css=v=>style.getPropertyValue(v).trim();
const colors=[css('--accent'),css('--accent2'),css('--negative'),css('--muted')],ink=css('--ink'),muted=css('--muted'),rule=css('--rule'),bg2=css('--bg2');
const chart=echarts.init($('#curves'),null,{renderer:'svg'});
const refs=ids=>(ids||[]).map(n=>`<sup><a href="#cite-${n}">[${n}]</a></sup>`).join('');
const statusClass=s=>/候选/.test(s)?'candidate':/暂不|排除/.test(s)?'reject':'';
function filtered(){
 const q=$('#search').value.trim().toLowerCase(),status=$('#status').value,scope=$('#scope').value;
 return Object.values(D.funds).filter(f=>f.status!=='排除'&&(scope==='all'||scope==='new'&&f.origin==='new'||scope==='existing'&&f.origin==='existing')&&(!status||f.status===status)&&(!q||[f.name,f.code,...f.manager,f.group,f.why].join(' ').toLowerCase().includes(q)));
}
function ordered(rows){
 const sort=$('#sort').value;
 return rows.sort((a,b)=>{
  if(sort==='decision')return a.order-b.order||a.name.localeCompare(b.name,'zh');
  const av=a.metrics[period]?.[sort],bv=b.metrics[period]?.[sort];
  if(!Number.isFinite(av))return 1;if(!Number.isFinite(bv))return -1;
  return sort==='vol'?av-bv:bv-av;
 });
}
function renderTable(){
 const rows=ordered(filtered());
 $('#count-note').textContent='显示 '+rows.length+' 项｜净值比较统一截至 '+D.nav_cutoff+'｜所选 '+D.period_labels[period]+'；起点遇非交易日取前一可得净值。';
 $('#fund-table tbody').innerHTML=rows.map(f=>{
  const m=f.metrics[period],x=f.marginal10;
  return `<tr><td class="fund-title"><a href="#fund-${f.code}" data-open="${f.code}">${esc(f.name)}</a><small>${f.code} · ${esc(f.manager.join(' / '))}</small><small>${esc(f.group)} ${refs(f.source_ids.slice(0,2))}</small></td><td><span class="pill ${statusClass(f.status)}">${esc(f.status)}</span></td><td class="num">${pct(m?.return)}</td><td class="num">${pct(m?.mdd)}</td><td class="num">${m?plain(m.vol*100):'—'}</td><td class="num">${pct(m?.current_dd)}</td><td class="num">${m?m.recovery_date||'尚未修复':'历史不足'}</td><td class="num">${pp(x?.return_delta)}</td><td class="num">${pp(x?.mdd_delta)}</td><td><button data-curve="${f.code}" type="button">加入曲线</button></td></tr>`;
 }).join('')||'<tr><td colspan="10" class="empty">没有匹配项，清空条件后重试。</td></tr>';
 renderCards(rows);
}
function renderCards(rows){
 $('#reviews').innerHTML=rows.map(f=>{
  const stages=Array.isArray(f.tenure)?f.tenure.map(x=>`${x.start}—${x.end||'至今'}：${x.manager||(x.managers||[]).join('/')} ${x.mode||''}`).join('；'):f.tenure;
  const m=f.metrics['3Y'],roll=f.rolling12;
  const stage=f.stage_metrics?`${f.stage_metrics.mode} ${f.stage_metrics.start}—${f.stage_metrics.end}，${f.stage_metrics.n}个净值区间：收益${pct(f.stage_metrics.return)}，回撤${pct(f.stage_metrics.mdd)}。${f.stage_metrics.n<120?'阶段短，不能视为周期能力证明。':''}`:'现任阶段回放未齐，不能把产品长历史全部归给现任。';
  return `<details class="fundcard" id="fund-${f.code}"><summary><div class="card-title"><h3>${esc(f.name)}</h3><span class="pill ${statusClass(f.status)}">${esc(f.status)}</span></div><div class="card-meta">${f.code} · ${esc(f.manager.join(' / '))} · ${esc(f.group)} ${refs(f.source_ids)}</div><p class="card-decision">${esc(f.why)}</p><p class="negative">${esc(f.counter)}</p></summary><dl class="factpairs"><dt>角色与替换</dt><dd>${esc(f.replace)}</dd><dt>升级条件</dt><dd>${esc(f.trigger)}</dd><dt>失效条件</dt><dd>${esc(f.failure)}</dd><dt>任期归因</dt><dd>${esc(f.manager_note||stages||'当前独管起点未取得；产品历史不归单人。')}<br>${esc(stage)}</dd><dt>持仓/规模</dt><dd>${esc(f.equity_note||'供数平台股票占净比 '+plain(f.equity_feed)+'，ETF/衍生品需穿透。')}${f.size_note?'<br>'+esc(f.size_note):''}</dd><dt>费用与可买性</dt><dd>${esc(f.fees||'费率与当前渠道未完成独立核验；净值已含日常费，不含个人交易摩擦。')}<br>${esc(f.execution||'申购限额/赎回档次未取得正式当日确认。')}</dd><dt>多周期诊断</dt><dd>${m?'三年回报 '+pct(m.return)+'，回撤 '+pct(m.mdd)+'，距前高 '+pct(m.current_dd)+'。':'原生份额不足三年，留空。'}<br>${roll?.count?'过去'+roll.count+'个月末的重叠12月窗口：最低 '+pct(roll.min)+'，中位 '+pct(roll.median)+'，正收益占比 '+plain(roll.positive_share*100)+'；不是独立样本或未来概率。':'滚动窗口不足。'}</dd><dt>年度证据</dt><dd>${Object.entries(f.annual||{}).map(([y,x])=>y+(y==='2026'?'年至11.19':'年')+'：'+pct(x?.return)).join('；')}</dd><dt>证据级别</dt><dd>${esc(f.evidence_note)}${f.quarter_check?'<br>2026Q3原文 '+plain(f.quarter_check.official_q3_pct)+'，重算 '+plain(f.quarter_check.calculated_pct)+'，差 '+f.quarter_check.difference_pp.toFixed(4)+'个百分点。':''}</dd><dt>缺项</dt><dd>${esc(f.gap_note||'全部重仓的同日估值、盈利修正和交易摩擦未齐；自动筛查不是实时人工判断。')}</dd></dl><div class="source-links">${(f.source_ids||[]).map(n=>`<a href="#cite-${n}">来源${n}</a>`).join('')}<button type="button" data-curve="${f.code}">放到曲线对比</button></div></details>`;
 }).join('');
}
function startFor(period){
 const end=new Date(D.nav_cutoff+'T00:00:00Z'),months=D.periods[period],year=end.getUTCFullYear(),m=end.getUTCMonth()-months,day=end.getUTCDate();
 return new Date(Date.UTC(year,m,Math.min(day,new Date(Date.UTC(year,m+1,0)).getUTCDate()))).toISOString().slice(0,10);
}
function renderChart(){
 const wanted=selected.map(c=>D.funds[c]).filter(Boolean).map(f=>({name:f.name,code:f.code,curve:f.curve}));
 if(showBase)wanted.push({name:'当前首选五基金（研究基线）',code:'BASE',curve:D.reference.curve});
 const start=startFor(period),unavailable=[],usable=[];
 for(const f of wanted){if(!f.curve?.length||f.curve[0][0]>start){unavailable.push(f.name);continue}usable.push(f)}
 $('#chart-note').textContent=unavailable.length?'历史不足，已明确排除这些曲线：'+unavailable.join('、')+'。没有截短其余曲线，也没有拼接A/C。':'全部显示曲线使用公共净值日期，不是各取不同起点。拖动底部区间条可放大局部。';
 if(!usable.length){chart.clear();chart.setOption({title:{text:'所选基金没有完整'+D.period_labels[period]+'历史',textStyle:{color:muted,fontSize:16},left:'center',top:'middle'}});return}
 const maps=usable.map(f=>new Map(f.curve)),all=usable[0].curve.map(r=>r[0]).filter(d=>d<=D.nav_cutoff&&maps.every(m=>m.has(d))),before=all.filter(d=>d<=start),anchor=before.at(-1);
 if(!anchor){chart.clear();$('#chart-note').textContent='没有足够共同起点，换周期或基金后比较。';return}
 const dates=all.filter(d=>d>=anchor),drawdown=$('#view-mode').value==='drawdown';
 const values=usable.map((f,j)=>{let peak=maps[j].get(dates[0]);return dates.map(d=>{const v=maps[j].get(d);peak=Math.max(peak,v);return Number(((drawdown?v/peak-1:v/maps[j].get(dates[0])-1)*100).toFixed(5))})});
 $('#curve-caption').textContent=(drawdown?'回撤':'累计收益')+'｜'+dates[0]+'—'+dates.at(-1)+'｜'+(dates.length-1)+'个共同净值区间';
 chart.setOption({animation:false,color:colors,textStyle:{color:ink,fontFamily:'sans-serif'},tooltip:{trigger:'axis',appendToBody:true,backgroundColor:bg2,borderColor:rule,textStyle:{color:ink},valueFormatter:v=>v.toFixed(2)+'%'},legend:{data:usable.map(x=>x.name),top:14,textStyle:{color:muted,fontSize:11},type:'scroll'},grid:{left:62,right:24,top:70,bottom:78},xAxis:{type:'category',data:dates,axisLabel:{color:muted,fontSize:11},axisLine:{lineStyle:{color:rule}},boundaryGap:false},yAxis:{type:'value',axisLabel:{color:muted,formatter:v=>v+'%'},splitLine:{lineStyle:{color:rule}}},dataZoom:[{type:'inside',filterMode:'none'},{type:'slider',bottom:13,height:22,borderColor:rule,textStyle:{color:muted},fillerColor:colors[0]+'33',dataBackground:{lineStyle:{color:muted}}}],series:usable.map((f,j)=>({name:f.name,type:'line',data:values[j],showSymbol:false,lineStyle:{width:2},emphasis:{focus:'series'}}))},true);
}
function renderChoices(){
 $('#selected-curves').innerHTML=selected.map(c=>`<button type="button" data-unselect="${c}">${esc(D.funds[c].name)} ×</button>`).join('');
}
function addCurve(c){
 if(!selected.includes(c)){if(selected.length>=3){$('#chart-note').textContent='同图最多3只基金＋当前组合，请先移除一个。';$('#curve-section').scrollIntoView({behavior:'smooth'});return}selected.push(c)}
 renderChoices();renderChart();$('#curve-section').scrollIntoView({behavior:'smooth'});
}
document.addEventListener('click',e=>{
 const c=e.target.closest('[data-curve]')?.dataset.curve;if(c){addCurve(c);return}
 const o=e.target.closest('[data-open]')?.dataset.open;if(o){let card=$('#fund-'+o);if(!card&&D.funds[o]){$('#scope').value='all';$('#search').value='';$('#status').value='';renderTable();card=$('#fund-'+o)}if(card)card.open=true}
 const citation=e.target.closest('a[href^="#cite-"]');if(citation){const target=$(citation.getAttribute('href'));const section=target?.closest('details');if(section)section.open=true}
 const r=e.target.closest('[data-unselect]')?.dataset.unselect;if(r){selected=selected.filter(c=>c!==r);renderChoices();renderChart()}
});
$('#periods').addEventListener('click',e=>{const b=e.target.closest('[data-period]');if(!b)return;period=b.dataset.period;$('#periods').querySelectorAll('button').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b))});renderTable();renderChart()});
['search','status','scope','sort'].forEach(id=>$('#'+id).addEventListener(id==='search'?'input':'change',renderTable));
$('#base-check').addEventListener('change',e=>{showBase=e.target.checked;renderChart()});
$('#view-mode').addEventListener('change',renderChart);
$('#reset-curves').addEventListener('click',()=>{selected=['007466','006624','007343'];showBase=false;$('#base-check').checked=false;renderChoices();renderChart()});
$('#all-open').addEventListener('click',()=>document.querySelectorAll('.fundcard').forEach(x=>x.open=true));
$('#all-close').addEventListener('click',()=>document.querySelectorAll('.fundcard').forEach(x=>x.open=false));
$('#export-json').addEventListener('click',()=>{
 const blob=new Blob([JSON.stringify({asof:D.asof,period,scope:$('#scope').value,funds:filtered().map(f=>({code:f.code,name:f.name,status:f.status,metrics:f.metrics[period],why:f.why,counter:f.counter,trigger:f.trigger,failure:f.failure,sources:f.source_ids})),sources:D.sources},null,2)],{type:'application/json;charset=utf-8'});
 const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='2026-11-22候选评测.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
window.addEventListener('resize',()=>chart.resize());
renderTable();renderChoices();renderChart();
})();
