const LT=DATA.longtermDecision;
const lt$=s=>document.querySelector(s);
const ltName=c=>LT.funds[c]?.name||c;
const ltPct=(v,d=2)=>`${v>=0?'+':''}${(v*100).toFixed(d)}%`;
const ltAbs=(v,d=2)=>`${(v*100).toFixed(d)}%`;
const ltesc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const l5w=LT.plans.L5.weights_pct;
lt$('#lt-equity').textContent=LT.plans.L5.equity_q3_pct.toFixed(1)+'%';
lt$('#lt-allocation tbody').innerHTML=Object.entries(l5w).map(([c,w])=>{
const f=LT.funds[c];return `<tr><td>${ltesc(f.name)}<br><span class="small mono">${c} / ${ltesc(f.manager)}</span></td><td class="number">${w}%</td><td class="number">${(230*w/100).toFixed(1)}</td><td>${ltesc(f.role)}</td><td>${ltesc(f.failure)}</td></tr>`}).join('');
lt$('#lt-goals').innerHTML=[['长期增长','收益'],['损失与恢复','回撤＋修复'],['委托是否值得','扣费同风险增益']].map(([label,value])=>`<div><div class="value" style="font-size:24px">${value}</div><div class="label">${label}</div></div>`).join('');
function ltVariant(k){const p=LT.plans[k];lt$('#lt-plan-title').textContent=p.title;lt$('#lt-plan-reason').textContent=p.reason;
lt$('#lt-variant tbody').innerHTML=Object.entries(p.weights_pct).map(([c,w])=>{const delta=w-(l5w[c]||0);return `<tr><td>${ltesc(ltName(c))}<small class="mono">${c==='CASH'?'可控外部资金':c}</small></td><td class="number">${w}%</td><td class="number">${(230*w/100).toFixed(2)}</td><td class="number">${delta>0?'+':''}${delta.toFixed(1)}个百分点</td></tr>`}).join('');
lt$('#lt-trigger').textContent=p.trigger;lt$('#lt-cost').textContent=p.cost;lt$('#lt-invalid').textContent=p.invalidation}
lt$('#lt-tabs').addEventListener('click',e=>{const b=e.target.closest('[data-lt]');if(!b)return;lt$('#lt-tabs').querySelectorAll('button').forEach(x=>{x.classList.toggle('selected',x===b);x.setAttribute('aria-pressed',String(x===b))});ltVariant(b.dataset.lt)});ltVariant('L5');
lt$('#lt-stress tbody').innerHTML=['L5','L4','L90','K5','G6','D60','OLD_A','OLD_B'].map(k=>{const p=LT.plans[k];return `<tr><td>${ltesc(p.title)}</td><td class="number">${p.equity_q3_pct.toFixed(2)}%</td><td class="number negative">${(-p.equity_q3_pct*.2).toFixed(2)}%</td><td class="number">${p.stress20_wan.toFixed(2)}</td><td class="number">${p.weights_pct.CASH||0}%</td></tr>`}).join('');
const ltDefaultRows=['L5','L4','L90','OLD_A','OLD_B','D60','J5','K5','G6','B74'];
function drawLT(item,mode,peer){
const names=['L5',peer],colors=['#d7a777','#8eaba2'];const series=names.map(k=>item.modes[mode][k].wealth);
let min=Math.min(...series.flat()),max=Math.max(...series.flat());const pad=Math.max(.008,(max-min)*.13);min-=pad;max+=pad;
const x=i=>62+i/(item.dates.length-1)*866,y=v=>274-(v-min)/(max-min)*227;
const grid=Array.from({length:5},(_,i)=>{const v=min+(max-min)*i/4;return `<line x1="62" y1="${y(v)}" x2="928" y2="${y(v)}" stroke="#ffffff15"/><text x="48" y="${y(v)+4}" text-anchor="end" fill="#a9a398" font-size="12">${((v-1)*100).toFixed(1)}%</text>`}).join('');
const lines=series.map((s,j)=>`<path d="${s.map((v,i)=>(i?'L':'M')+x(i).toFixed(2)+','+y(v).toFixed(2)).join(' ')}" fill="none" stroke="${colors[j]}" stroke-width="${j?2:2.8}"/>`).join('');
lt$('#lt-wealth-chart').innerHTML=`<title>L5与${ltesc(LT.plans[peer].title)}同窗财富路径</title>${grid}${lines}${names.map((k,j)=>`<line x1="${62+j*300}" y1="22" x2="${84+j*300}" y2="22" stroke="${colors[j]}" stroke-width="3"/><text x="${92+j*300}" y="26" fill="${colors[j]}" font-size="14">${ltesc(LT.plans[k].title)}</text>`).join('')}<text x="62" y="310" fill="#a9a398" font-size="12">${item.start}</text><text x="928" y="310" fill="#a9a398" font-size="12" text-anchor="end">${item.end}</text>`;
}
function ltCompare(){
const window=lt$('#lt-window').value,mode=lt$('#lt-mode').value,peer=lt$('#lt-peer').value;
const item=LT.comparisons.global.windows[window],rows=item.modes[mode];
lt$('#lt-window-note').textContent=`${item.start}—${item.end}，${item.intervals}个共同区间；${mode==='fixed'?'期初配置后自然漂移':'每日恢复目标权重'}。现金收益设0，净值含日常运作费、未计持有人交易费与在途。日期和方式完全相同才比较；这是2026.11.22事后研究。`;
lt$('#lt-metrics tbody').innerHTML=ltDefaultRows.map(k=>{const m=rows[k].metrics;return `<tr class="${k==='L5'?'primary-row':''}"><td class="${k==='L5'?'lt-name':''}">${ltesc(LT.plans[k].title)}</td><td class="number ${m.return>=0?'positive':'negative'}">${ltPct(m.return)}</td><td class="number">${ltPct(m.mdd)}</td><td class="number">${ltAbs(m.vol)}</td><td class="number">${ltPct(m.current_drawdown)}</td><td class="number">${ltAbs(m.ulcer)}</td><td class="number">${LT.plans[k].equity_q3_pct.toFixed(2)}%</td></tr>`}).join('');
const a=rows.L5.metrics,b=rows[peer].metrics;const ret=(a.return-b.return)*100,dd=(a.mdd-b.mdd)*100;
lt$('#lt-fact-summary').innerHTML=`<strong>这个窗口：L5相对${ltesc(LT.plans[peer].title)}，收益${ret>=0?'多':'少'}${Math.abs(ret).toFixed(2)}个百分点，最大回撤${dd>=0?'浅':'深'}${Math.abs(dd).toFixed(2)}个百分点。</strong><p>这两个差值只描述同窗样本，不是统计显著性、预期收益或未来改进保证。${a.current_drawdown<-.00001?'L5仍未回到此窗前高。':'L5处于此窗前高附近。'}J5和K5有各自优势，D60损失更浅但参与度更低；不能只比较收益或只比较平滑。</p>`;
lt$('#lt-recovery tbody').innerHTML=['L5',peer].map(k=>{const m=rows[k].metrics,e=m.worst_episode;return `<tr><td>${ltesc(LT.plans[k].title)}</td><td>${e.peak}</td><td>${e.trough}</td><td>${e.recovered||'截至终点未修复'}</td><td>${e.days_peak_to_recovery===null?'未完成，不预测':e.days_peak_to_recovery+'日'}</td><td class="number">${m.current_underwater_calendar_days}</td></tr>`}).join('');
drawLT(item,mode,peer);
}
['lt-window','lt-mode','lt-peer'].forEach(id=>lt$('#'+id).addEventListener('change',ltCompare));ltCompare();
const domestic=LT.comparisons.domestic.windows.full.modes.fixed;
lt$('#lt-domestic tbody').innerHTML=Object.entries(domestic).map(([k,v])=>{const m=v.metrics;return `<tr><td>${ltesc(LT.plans[k].title)}</td><td>${ltPct(m.return)}</td><td>${ltPct(m.mdd)}</td><td>${ltAbs(m.vol)}</td><td>${ltPct(m.current_drawdown)}</td><td>${m.worst_episode.recovered?m.worst_episode.days_peak_to_recovery+'日（至'+m.worst_episode.recovered+'）':'截至终点未修复'}</td></tr>`}).join('');
lt$('#lt-source-note').textContent='原生CSV沿用11月21日已核证据（净值境内至11月20、QDII至11月19），共同网格为4月15—11月19；数据哈希、全部比较和独立复算在证据包。没有用最新读取日期冒充新的行情或完成跨周期验证。';
