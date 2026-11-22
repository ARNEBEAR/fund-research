const capitalCashAlternatives=[
{c:0,p:'明确愿承受较大回撤并认为股权价格有足够补偿',r:'原A并没有证明现时应该全额承担该股权风险'},
{c:30,p:'成长参与更高，同时保留一定流动性',r:'若信用/盈利压力共振，仍可能超过短期损失预算'},
{c:50,p:'在防守与参与之间分担不确定性',r:'一半风险预算也非硬损失上限；并非统计最优'},
{c:70,p:'以短期购买力和避免被动卖出优先的待机参照',r:'政策和价格先于宏观修复时，错过反弹的代价明显'},
{c:85,p:'近期开支、风险容忍极低或已核重大尾部压力',r:'没有同等严重证据时容易过度防御，长期实际购买力也受影响'}];
$('#cash-current-table tbody').innerHTML=capitalCashAlternatives.map(x=>`<tr><td class="mono">${x.c}%</td><td class="number">${(230*x.c/100).toFixed(1)}</td><td class="number">${(230*(1-x.c/100)).toFixed(1)}</td><td>${esc(x.p)}</td><td>${esc(x.r)}</td></tr>`).join('');
function updateLossBudget(){const l=Number($('#loss-budget').value)/100,s=Number($('#stock-shock').value)/100,e=DATA.plans.A.equity_q3,c=Math.max(0,1-l/(e*s));$('#loss-budget-value').textContent=plainPct(l,0);$('#stock-shock-value').textContent=plainPct(s,0);$('#cash-required').textContent='约 '+plainPct(c,1);$('#cash-risk-reason').textContent=`仅在这些假设同时成立时，约需 ${(230*c).toFixed(1)} 万现金，才能把静态映射控制在约 ${plainPct(l,0)}。70%现金在该股权冲击中仍约 ${pct(-.3*e*s,2)}，不是保证最大损失。`;}
$('#loss-budget').addEventListener('input',updateLossBudget);$('#stock-shock').addEventListener('input',updateLossBudget);updateLossBudget();
function dailyDate(x){return x?.date||x?.asof||x?.last_success||'未取得'}
async function loadDailyReview(){
 const box=$('#daily-review-status');
 if(location.protocol==='file:'){box.classList.add('daily-status-stale');box.innerHTML='<span class="eyebrow">OFFLINE SNAPSHOT</span><p>本地文件显示冻结内容。<a class="copper" href="https://arnebear.github.io/fund-research/proposals/2026-11-21/asymmetry/#current">打开线上最新审视 ↗</a>；不会伪造本地日更状态。</p>';return}
 async function read(p){try{const r=await fetch(p,{cache:'no-store'});if(!r.ok)return null;return await r.json()}catch{return null}}
 const evidence=await read('daily/latest.json'),semantic=await read('daily/semantic-latest.json'),status=await read('daily/semantic-status.json');
 const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const last=dailyDate(semantic),stale=!semantic||last!==today;
 box.classList.toggle('daily-status-stale',stale);
 box.innerHTML=`<span class="eyebrow">DAILY AUDIT / ${stale?'尚未完成今日全量语义复核':'今日语义覆盖完成，仍有证据边界'}</span><p>证据日期 ${esc(dailyDate(evidence))} · 最近语义成功 ${esc(last)} · 最新尝试 ${esc(status?.attempted_at||'未取得')}<br>状态 ${esc(status?.state||'尚未取得模型状态')}。${stale?'旧内容只按原日期参考，不能当作今日已核。':'模型送审覆盖与反方复核通过，不等同每条事实均独立证实。'}</p>`;
 if(semantic?.synthesis){const s=semantic.synthesis;$('#daily-semantic-summary').innerHTML=`<div class="daily-summary-card"><span class="eyebrow">${esc(semantic.date)} / GitHub Models ${esc(semantic.model)}</span><h3 style="margin-top:15px">${esc(s.headline)}</h3><p>${esc(s.market_regime)}</p><p><strong>研究倾向：</strong>${esc(s.stance)}</p><div class="columns"><div><h4>高现金支持</h4><p>${esc(s.cash70_case)}</p></div><div><h4>最强反证与代价</h4><p>${esc(s.cash70_countercase)}</p></div></div><p class="small">覆盖 ${esc(semantic.coverage?.reviewed)} 项 · 未核：${esc((s.unverified||[]).join('；'))}</p>${(s.changes||[]).map(c=>`<div class="daily-review-correction"><span class="eyebrow">${esc(c.target)}</span><p>${esc(c.reason)}</p><p>${esc(c.replacement)}</p></div>`).join('')}<p class="small">反方意见：${esc((semantic.counter_review?.objections||[]).join('；'))}</p></div>`;}
 const rows=semantic?.items||[];
 if(rows.length)$('#daily-claim-ledger').innerHTML=`<details><summary>展开全部逐项送审状态与需要更新的内容</summary><p class="small">同一模型结论须对照原文；historical_retained只是按历史保留，insufficient_current_evidence不能转成已核。</p>${rows.map(r=>`<div class="daily-ledger-row"><span class="mono">${esc(r.item_id)}</span> · ${esc(r.status)}<br>${esc(r.reason)}<br><small>来源 ${esc((r.sources||[]).join(' / ')||'无新证据')}</small></div>`).join('')}</details>`;
}
loadDailyReview();
