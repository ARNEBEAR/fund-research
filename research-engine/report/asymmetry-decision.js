const DEC=DATA.currentDecision;
const frole=code=>DEC.funds[code]||{name:code,role:'明确市场敞口',failure:'市场与执行风险'};
const currentW=DEC.plans.D60.weights_pct;
const eq=p=>Object.entries(p.weights_pct).reduce((n,[c,w])=>n+w/100*(DEC.funds[c]?.equity_pct||0)/100,0);
function decisionRows(p,compare=false){return Object.entries(p.weights_pct).map(([c,w])=>`<tr><td>${esc(frole(c).name)}${c==='CASH'?'':`<br><span class="small mono">${c}</span>`}</td><td class="number">${w}%</td><td class="number">${(230*w/100).toFixed(1)}</td>${compare?`<td class="number">${w-currentW[c]>0?'+':''}${w-currentW[c]}个百分点</td>`:`<td>${esc(frole(c).role)}</td><td>${esc(frole(c).failure)}</td>`}</tr>`).join('')}
$('#decision-allocation tbody').innerHTML=decisionRows(DEC.plans.D60);
const ce=eq(DEC.plans.D60);
$('#decision-risk-line').innerHTML=[['60%现金方案的股权敞口',plainPct(ce,1)],['人工共同股权−20%',pct(-ce*.2,1)],['对应静态损失',(230*ce*.2).toFixed(2)+'万']].map(([l,v])=>`<div><div class="value">${v}</div><div class="label">${l}</div></div>`).join('');
function showDecision(k){const p=DEC.plans[k];$('#decision-plan-title').textContent=p.title;$('#decision-plan-thesis').textContent=p.thesis;$('#decision-variant-table tbody').innerHTML=decisionRows(p,true);$('#decision-plan-trigger').textContent=p.trigger;$('#decision-plan-cost').textContent=p.cost;$('#decision-plan-invalid').textContent=p.invalidation;}
$('#decision-tabs').addEventListener('click',e=>{const b=e.target.closest('[data-decision]');if(!b)return;$('#decision-tabs').querySelectorAll('button').forEach(x=>x.classList.toggle('selected',x===b));showDecision(b.dataset.decision)});showDecision('D60');
$('#decision-stress-table tbody').innerHTML=Object.entries(DEC.plans).map(([k,p])=>{const e=eq(p);return `<tr><td>${p.title}</td><td class="number">${plainPct(e,1)}</td><td class="number negative">${pct(-e*.2,1)}</td><td class="number">${(230*e*.2).toFixed(2)}</td><td class="number positive">${pct(e*.2,1)}</td></tr>`}).join('');
function updateDecisionBudget(){const l=Number($('#loss-budget').value)/100,s=Number($('#stock-shock').value)/100,e=ce/.4,c=Math.max(0,1-l/(e*s));$('#loss-budget-value').textContent=plainPct(l,0);$('#stock-shock-value').textContent=plainPct(s,0);$('#cash-required').textContent='约 '+plainPct(c,1);$('#cash-risk-reason').textContent=`若基金内部保持原60%现金方案的五基金结构，仅在这些假设下约需 ${(230*c).toFixed(1)} 万外部现金；60%现金仍约 ${pct(-ce*s,2)}。这是压力约束，不是未来概率、实际最大损失或唯一最优。`;}
$('#loss-budget').addEventListener('input',updateDecisionBudget);$('#stock-shock').addEventListener('input',updateDecisionBudget);updateDecisionBudget();
const passive={
'CASH':{name:'外部现金',note:'人民币购买力、可用性与具体工具另核；不以在途或理财风险等级冒充。'},
'110020':{name:'易方达沪深300ETF联接A',note:'国内宽基；管理＋托管标示费率0.20%/年，非全部成本。标准申购1.20%（100万以下）、7—364日赎回0.50%，渠道折扣未核。短期使用须重算成本；市场与权重股风险不变。'},
'513500':{name:'博时标普500ETF',note:'美国宽基、QDII及人民币汇率风险；场内溢价和申购状态须核，不能以价格涨幅代替NAV回报。'},
'011066':{name:'大成高鑫C',note:'保留一个主动质量委托，制造/出口与买价风险仍需持续核验。'}};
$('#independent-allocation tbody').innerHTML=Object.entries(DEC.unconstrained.weights_pct).map(([c,w])=>`<tr><td>${passive[c].name}${c==='CASH'?'':`<br><span class="small mono">${c}</span>`}</td><td class="number">${w}%</td><td class="number">${(230*w/100).toFixed(1)}</td><td>${esc(passive[c].note)}</td></tr>`).join('');
$('#independent-source-note').innerHTML=`<p class="small">下列工具已作身份/费用来源核查；渠道、价格、净值日及限额不同，不能用一种状态代表所有渠道。${(DEC.passiveSources||[]).map(s=>`<a class="copper" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)} ↗</a>`).join(' · ')}<br>${esc(DEC.passiveLimit||'U60为条件替代；未取得完整实时渠道与溢价，不把预算记为可执行。')}</p>`;
$('#content-score').textContent=DEC.document_content_score.score+'/100';
$('#content-score-dimensions').innerHTML=DEC.document_content_score.dimensions.map(s=>`<tr><td>${esc(s.name)}</td><td class="number">${s.score}/${s.out_of}</td><td>${esc(s.reason)}</td></tr>`).join('');
$('#document-claim-summary').innerHTML=DATA.doc100.claims.filter(c=>c.topic!=='账户'&&c.status!=='excluded_unrelated_owner_account').map(c=>`<details><summary>${esc(c.id)} · ${esc(c.title)} <span class="tag ${c.status.startsWith('已核')?'verified':'inference'}">${esc(c.status)}</span></summary><p>${esc(c.conclusion)}</p><p class="small">${esc(c.impact)}</p></details>`).join('');
async function loadDecisionDaily(){const box=$('#daily-review-status');if(location.protocol==='file:'){box.innerHTML='<span class="eyebrow">本地冻结副本</span><p>最新日审请以线上状态为准。</p>';return}
 async function read(p){try{const r=await fetch(p,{cache:'no-store'});return r.ok?await r.json():null}catch{return null}}
 const evidence=await read('daily/latest.json'),semantic=await read('daily/semantic-latest.json'),status=await read('daily/semantic-status.json');
 const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const fresh=semantic?.date===today&&semantic?.state==='completed_with_counter_review';
 box.innerHTML=`<span class="eyebrow">DAILY REVIEW / ${fresh?'逐项语义覆盖完成，证据边界仍保留':'证据审视与语义审议状态分开'}</span><p>最近证据 ${esc(evidence?.asof||'未取得')} · 查询成功 ${esc(evidence?.coverage?.success??'—')}/${esc(evidence?.coverage?.attempted??'—')} · 最近语义成功 ${esc(semantic?.date||'尚未完成')}<br>最新尝试 ${esc(status?.attempted_at||'未取得')} · ${esc(status?.state||'无状态')}。${esc(status?.detail||'逐项送审不等于每条事实都已独立确证。')}</p>`;
 if(semantic?.synthesis){const s=semantic.synthesis;$('#daily-semantic-summary').innerHTML=`<div class="daily-summary-card"><span class="eyebrow">${esc(semantic.date)} / 模型审议，非人工全知核验</span><h3 style="margin-top:15px">${esc(s.headline)}</h3><p>${esc(s.stance)}</p><p class="small">${esc(s.market_regime)}</p>${(s.changes||[]).map(c=>`<details><summary>${esc(c.target)} · 修改理由</summary><p>${esc(c.reason)}</p><p>${esc(c.replacement)}</p></details>`).join('')}</div>`;}
}
loadDecisionDaily();
