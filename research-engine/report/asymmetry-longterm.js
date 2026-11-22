const LT=DATA.longtermDecision;
const lt$=s=>document.querySelector(s);
const ltName=c=>LT.funds[c]?.name||c;
const ltPct=(v,d=2)=>`${v>=0?'+':''}${(v*100).toFixed(d)}%`;
const ltAbs=(v,d=2)=>`${(v*100).toFixed(d)}%`;
const ltesc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ltLabels={
L5:{title:'长期五基金：质量与估值纪律',short:'长期五基金',difference:'本轮长期候选；广发与高鑫为较大核心，保留价值、产业和海外。'},
L4:{title:'国内四基金：取消海外',short:'国内四基金',difference:'取消交银环球，高鑫和前海各增加5个百分点。'},
L90:{title:'五基金＋10%外部现金',short:'五基金＋10%现金',difference:'长期五基金的比例各缩小10%，留出10%可控资金。'},
OLD_A:{title:'原八基金：均衡参与',short:'原八基金',difference:'2026.11.21原提案，含万家、科益和交银优势；非用户已核现仓。'},
OLD_B:{title:'原七基金：更多科技与海外',short:'原七基金',difference:'相对原八基金取消交银优势，提高科益、万家与交银环球。'},
D60:{title:'60%现金＋五基金：阶段防守',short:'60%现金防守',difference:'旧短期风险提案，基金合计40%；不作为长期默认结构。'},
D70:{title:'70%现金＋五基金：加强防守',short:'70%现金防守',difference:'旧短期提案，基金合计30%，进一步降低科益及海外权重。'},
R40:{title:'40%现金＋五基金：参与修复',short:'40%现金参与修复',difference:'旧短期提案，基金合计60%，提高质量、科技与海外参与。'},
J5:{title:'另一网站五基金：含国泰致和',short:'含致和的五基金',difference:'广发、前海各30%；以国泰致和替代常驻海外席，高鑫占15%。'},
K5:{title:'开阳替代高鑫：质量候选',short:'开阳替代高鑫',difference:'高鑫25%全部换为中泰开阳，其余比例与长期五基金相同。'},
G6:{title:'五基金＋科益：增加成长',short:'增加10%科益',difference:'广发和高鑫各减5个百分点，增加10%科益成长卫星。'},
B74:{title:'沪深300＋标普＋现金：市场参照',short:'宽基＋现金参照',difference:'按长期五基金的披露股权强度近似配置；只作研究参照。'}
};
const ltTitle=k=>ltLabels[k]?.title||LT.plans[k]?.title||k;
const ltShort=k=>ltLabels[k]?.short||ltTitle(k);
const ltReadable=s=>String(s??'').replace(/\b(L5|L4|L90|K5|G6|D60|D70|R40|J5|B74)\b/g,k=>ltShort(k));
const ltWeight=w=>Number.isInteger(w)?String(w):w.toFixed(2).replace(/0+$/,'').replace(/\.$/,'');
function ltComposition(k){return Object.entries(LT.plans[k].weights_pct).map(([c,w])=>`<span>${ltesc(ltName(c))}<b>${ltWeight(w)}%</b></span>`).join('')}
function ltPlanCell(k){return `<div class="lt-plan-heading">${ltesc(ltTitle(k))}</div><p class="lt-plan-difference">${ltesc(ltLabels[k]?.difference||'')}</p><div class="lt-composition" aria-label="基金与期初目标比例">${ltComposition(k)}</div>`}
const l5w=LT.plans.L5.weights_pct;
lt$('#lt-equity').textContent=LT.plans.L5.equity_q3_pct.toFixed(1)+'%';
lt$('#lt-allocation tbody').innerHTML=Object.entries(l5w).map(([c,w])=>{
const f=LT.funds[c];return `<tr><td>${ltesc(f.name)}<br><span class="small mono">${c} / ${ltesc(f.manager)}</span></td><td class="number">${w}%</td><td class="number">${(230*w/100).toFixed(1)}</td><td>${ltesc(f.role)}</td><td>${ltesc(f.failure)}</td></tr>`}).join('');
lt$('#lt-goals').innerHTML=[['长期增长','收益'],['损失与恢复','回撤＋修复'],['委托是否值得','扣费同风险增益']].map(([label,value])=>`<div><div class="value" style="font-size:24px">${value}</div><div class="label">${label}</div></div>`).join('');
function ltVariant(k){const p=LT.plans[k];lt$('#lt-plan-title').textContent=ltTitle(k);lt$('#lt-plan-reason').textContent=ltReadable(p.reason);
lt$('#lt-variant tbody').innerHTML=Object.entries(p.weights_pct).map(([c,w])=>{const delta=w-(l5w[c]||0);return `<tr><td>${ltesc(ltName(c))}<small class="mono">${c==='CASH'?'可控外部资金':c}</small></td><td class="number">${w}%</td><td class="number">${(230*w/100).toFixed(2)}</td><td class="number">${delta>0?'+':''}${delta.toFixed(1)}个百分点</td></tr>`}).join('');
lt$('#lt-trigger').textContent=ltReadable(p.trigger);lt$('#lt-cost').textContent=ltReadable(p.cost);lt$('#lt-invalid').textContent=ltReadable(p.invalidation)}
lt$('#lt-tabs').addEventListener('click',e=>{const b=e.target.closest('[data-lt]');if(!b)return;lt$('#lt-tabs').querySelectorAll('button').forEach(x=>{x.classList.toggle('selected',x===b);x.setAttribute('aria-pressed',String(x===b))});ltVariant(b.dataset.lt)});ltVariant('L5');
lt$('#lt-stress tbody').innerHTML=['L5','L4','L90','K5','G6','D60','OLD_A','OLD_B'].map(k=>{const p=LT.plans[k];return `<tr><td class="lt-plan-cell">${ltPlanCell(k)}</td><td class="number">${p.equity_q3_pct.toFixed(2)}%</td><td class="number negative">${(-p.equity_q3_pct*.2).toFixed(2)}%</td><td class="number">${p.stress20_wan.toFixed(2)}</td><td class="number">${p.weights_pct.CASH||0}%</td></tr>`}).join('');
const ltDefaultRows=['L5','L4','L90','OLD_A','OLD_B','D60','J5','K5','G6','B74'];
function drawLT(item,mode,peer){
const names=['L5',peer],colors=['#d7a777','#8eaba2'];const series=names.map(k=>item.modes[mode][k].wealth);
let min=Math.min(...series.flat()),max=Math.max(...series.flat());const pad=Math.max(.008,(max-min)*.13);min-=pad;max+=pad;
const x=i=>62+i/(item.dates.length-1)*866,y=v=>274-(v-min)/(max-min)*227;
const grid=Array.from({length:5},(_,i)=>{const v=min+(max-min)*i/4;return `<line x1="62" y1="${y(v)}" x2="928" y2="${y(v)}" stroke="#ffffff15"/><text x="48" y="${y(v)+4}" text-anchor="end" fill="#a9a398" font-size="12">${((v-1)*100).toFixed(1)}%</text>`}).join('');
const lines=series.map((s,j)=>`<path d="${s.map((v,i)=>(i?'L':'M')+x(i).toFixed(2)+','+y(v).toFixed(2)).join(' ')}" fill="none" stroke="${colors[j]}" stroke-width="${j?2:2.8}"/>`).join('');
lt$('#lt-wealth-chart').innerHTML=`<title>${ltesc(ltTitle('L5'))}与${ltesc(ltTitle(peer))}同窗财富路径</title>${grid}${lines}${names.map((k,j)=>`<line x1="${62+j*390}" y1="22" x2="${84+j*390}" y2="22" stroke="${colors[j]}" stroke-width="3"/><text x="${92+j*390}" y="26" fill="${colors[j]}" font-size="14">${ltesc(ltShort(k))}</text>`).join('')}<text x="62" y="310" fill="#a9a398" font-size="12">${item.start}</text><text x="928" y="310" fill="#a9a398" font-size="12" text-anchor="end">${item.end}</text>`;
}
function ltCompare(){
const window=lt$('#lt-window').value,mode=lt$('#lt-mode').value,peer=lt$('#lt-peer').value;
const item=LT.comparisons.global.windows[window],rows=item.modes[mode];
lt$('#lt-window-note').textContent=`${item.start}—${item.end}，${item.intervals}个共同区间；${mode==='fixed'?'期初配置后自然漂移':'每日恢复目标权重'}。现金收益设0，净值含日常运作费、未计持有人交易费与在途。日期和方式完全相同才比较；这是2026.11.22事后研究。`;
lt$('#lt-selected-plans').innerHTML=['L5',peer].map(k=>`<div class="lt-selected-card"><span class="eyebrow">${k==='L5'?'本轮长期候选':'当前曲线对照'}</span>${ltPlanCell(k)}</div>`).join('');
lt$('#lt-metrics tbody').innerHTML=ltDefaultRows.map(k=>{const m=rows[k].metrics;return `<tr class="${k==='L5'?'primary-row':''}"><td class="lt-plan-cell ${k==='L5'?'lt-name':''}">${ltPlanCell(k)}</td><td class="number ${m.return>=0?'positive':'negative'}">${ltPct(m.return)}</td><td class="number">${ltPct(m.mdd)}</td><td class="number">${ltAbs(m.vol)}</td><td class="number">${ltPct(m.current_drawdown)}</td><td class="number">${ltAbs(m.ulcer)}</td><td class="number">${LT.plans[k].equity_q3_pct.toFixed(2)}%</td></tr>`}).join('');
const a=rows.L5.metrics,b=rows[peer].metrics;const ret=(a.return-b.return)*100,dd=(a.mdd-b.mdd)*100;
lt$('#lt-fact-summary').innerHTML=`<strong>这个窗口：长期五基金相对“${ltesc(ltTitle(peer))}”，收益${ret>=0?'多':'少'}${Math.abs(ret).toFixed(2)}个百分点，最大回撤${dd>=0?'浅':'深'}${Math.abs(dd).toFixed(2)}个百分点。</strong><p>这两个差值只描述同窗样本，不是统计显著性、预期收益或未来改进保证。${a.current_drawdown<-.00001?'长期五基金仍未回到此窗前高。':'长期五基金处于此窗前高附近。'}含国泰致和的五基金与开阳替代方案有各自优势，60%现金方案损失更浅但参与度更低；不能只比较收益或只比较平滑。</p>`;
lt$('#lt-recovery tbody').innerHTML=['L5',peer].map(k=>{const m=rows[k].metrics,e=m.worst_episode;return `<tr><td class="lt-plan-cell">${ltPlanCell(k)}</td><td>${e.peak}</td><td>${e.trough}</td><td>${e.recovered||'截至终点未修复'}</td><td>${e.days_peak_to_recovery===null?'未完成，不预测':e.days_peak_to_recovery+'日'}</td><td class="number">${m.current_underwater_calendar_days}</td></tr>`}).join('');
drawLT(item,mode,peer);
}
['lt-window','lt-mode','lt-peer'].forEach(id=>lt$('#'+id).addEventListener('change',ltCompare));ltCompare();
const domestic=LT.comparisons.domestic.windows.full.modes.fixed;
lt$('#lt-domestic tbody').innerHTML=Object.entries(domestic).map(([k,v])=>{const m=v.metrics;return `<tr><td class="lt-plan-cell">${ltPlanCell(k)}</td><td>${ltPct(m.return)}</td><td>${ltPct(m.mdd)}</td><td>${ltAbs(m.vol)}</td><td>${ltPct(m.current_drawdown)}</td><td>${m.worst_episode.recovered?m.worst_episode.days_peak_to_recovery+'日（至'+m.worst_episode.recovered+'）':'截至终点未修复'}</td></tr>`}).join('');
lt$('#lt-source-note').textContent='原生CSV沿用11月21日已核证据（净值境内至11月20、QDII至11月19），共同网格为4月15—11月19；数据哈希、全部比较和独立复算在证据包。没有用最新读取日期冒充新的行情或完成跨周期验证。';
