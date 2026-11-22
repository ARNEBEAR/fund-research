(function(){
'use strict';
const W=DATA.workbench,E=window.PortfolioEngine,$=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=(n,d=2)=>Number.isFinite(n)?(n>=0?'+':'')+(n*100).toFixed(d)+'%':'—';
const plain=(n,d=1)=>Number.isFinite(n)?n.toFixed(d)+'%':'未核';
const num=(n,d=2)=>Number(n.toFixed(d)).toString();
const clone=o=>JSON.parse(JSON.stringify(o));
const colors=['#d8ad7a','#92b8ae','#a7a1cf','#c98c82'];
const periodName=p=>({'1M':'一个月','3M':'三个月','6M':'六个月','1Y':'一年','2Y':'两年','ALL':'全部可得'}[p]||'自定义');
const STORE='asymmetry-custom-portfolios-v15';
const funds=clone(W.funds);
const names={L5:'长期五基金：质量与估值纪律',L4:'国内四基金：取消海外',L90:'五基金＋10%外部现金',K5:'开阳替代高鑫',G6:'增加10%科益',D60:'60%现金＋五基金',D70:'70%现金＋五基金',R40:'40%现金＋五基金',OLD_A:'原八基金：均衡参与',OLD_B:'原七基金：更多科技与海外',J5:'另一网站含致和的五基金',B74:'沪深300＋标普＋现金参照'};
let saved=[],selected=['L5'],weights=clone(W.reference_weights),draftName='我的长期研究组合';
let period='3M',allowPartial=false,customDates=null,result=null,effects=[],view=null,drag=null,focusIndex=null,debounce;
const plans=Object.fromEntries(Object.entries(W.prior_plans).map(([k,p])=>[k,{id:k,name:names[k]||p.title,weights:p.weights_pct}]));
function message(text){$('#wb-message').textContent=text}
function fundLabel(c){return funds[c]?.name||c}
function allocation(w){return Object.entries(w).filter(([c,x])=>x>0).map(([c,x])=>fundLabel(c)+' '+num(x)+'%').join(' · ')}
function validImported(f){
 return f&&typeof f.name==='string'&&f.name.length<=100&&Array.isArray(f.nav)&&f.nav.length>=3&&f.nav.length<=30000&&f.nav.every((r,i)=>Array.isArray(r)&&E.validDate(r[0])&&Number.isFinite(r[1])&&r[1]>0&&(!i||r[0]>f.nav[i-1][0]));
}
function importedRecord(f){return {code:String(f.code||'').slice(0,6),name:f.name,nav:f.nav,
 first_date:f.nav[0][0],data_asof:f.nav.at(-1)[0],imported:true,equity_pct:null,family:'unknown',
 sources:[],role:'用户指定基金，职责待核',tenure:'经理阶段未独立核验',thesis:'用户提供的财富序列，仅核数据格式。',
 risk:'持仓、基金身份、费用和买价资料尚未核，暂不完整评级。',evidence_level:'用户导入，不是已核证据'};}
try{
 const stored=JSON.parse(localStorage.getItem(STORE)||'null');
 if(stored?.version===1&&Array.isArray(stored.portfolios)){
  for(const [k,f] of Object.entries(stored.imported||{}))if(/^(?:IMPORTED_)?\d{6}$/.test(k)&&validImported(f)&&(!funds[k]||funds[k].imported))funds[k]=importedRecord(f);
  saved=stored.portfolios.slice(0,12).filter(p=>typeof p.name==='string'&&p.name.length<=70&&!E.validateWeights(p.weights)&&Object.keys(p.weights).every(c=>funds[c]));
 }
}catch{}
function presetOptions(){
 $('#wb-preset').innerHTML='<option value="">选择一个方案作为编辑起点</option>'+Object.entries(plans).map(([k,p])=>`<option value="${k}">${esc(p.name)}</option>`).join('')+saved.map((p,i)=>`<option value="SAVED_${i}">已保存：${esc(p.name)}</option>`).join('');
}
function planByKey(k){if(k.startsWith('SAVED_'))return saved[Number(k.slice(6))];return plans[k]}
function refreshList(){
 $('#wb-fund-list').innerHTML=Object.entries(funds).map(([k,f])=>`<option value="${esc(k)}">${esc(f.name)} / ${esc(f.manager||'资料待核')}</option>`).join('');
}
function renderEditor(){
 $('#wb-name').value=draftName;
 $('#wb-rows').innerHTML=Object.entries(weights).map(([c,w])=>`<div class="wb-allocation-row"><div class="wb-fund-name">${esc(fundLabel(c))}<small>${esc(funds[c]?.code||c)}${funds[c]?.imported?' · 用户导入/待核':''}</small></div><input type="number" step="0.1" min="0" max="100" value="${num(w,6)}" data-weight="${esc(c)}" aria-label="${esc(fundLabel(c))}比例"><button type="button" data-remove="${esc(c)}" aria-label="移除${esc(fundLabel(c))}">×</button></div>`).join('');
 updateTotal();
}
function updateTotal(){
 const sum=Object.values(weights).reduce((n,w)=>n+w,0),valid=!E.validateWeights(weights);
 $('#wb-total').textContent=sum.toFixed(2)+'%';$('#wb-total').className=valid?'wb-total-ok':'wb-total-bad';
}
function compareList(){
 const keys=['L5','OLD_A','D60','K5',...saved.map((p,i)=>'SAVED_'+i)];
 if(plans.EXPERIMENT_BASE)keys.push('EXPERIMENT_BASE');
 $('#wb-compare-list').innerHTML='<span class="small">加到同图（最多3项对照）</span>'+keys.map(k=>`<label><input type="checkbox" value="${esc(k)}" ${selected.includes(k)?'checked':''}>${esc(planByKey(k)?.name||k)}</label>`).join('');
}
function options(){
 return {period,mode:$('#wb-mode').value,cashRate:Number($('#wb-cash-rate').value),allowPartial,...(customDates||{})};
}
function currentPlan(){return {id:'CUSTOM',name:draftName.trim()||'我的研究组合',weights:clone(weights)}}
function getCompared(){return [currentPlan(),...selected.map(k=>{const p=planByKey(k);return p?{...clone(p),id:k}:null}).filter(Boolean)]}
function showError(r){
 $('#wb-data-warning').textContent=r.error;$('#wb-partial').hidden=r.kind!=='short';
 $('#wb-sample-note').textContent='数据缺项时不会生成完整区间曲线。结构判断仍可阅读，历史指标暂不计算。';
 $('#wb-chart').innerHTML='<text x="460" y="175" text-anchor="middle" fill="#a9a398" font-size="19">等待完整比例和共同净值</text><text x="460" y="205" text-anchor="middle" fill="#8c877f" font-size="13">先处理下方数据说明，再观察曲线</text>';
 $('#wb-metrics tbody').innerHTML='';$('#wb-tooltip').hidden=true;
 ['#wb-export-csv','#wb-export-svg'].forEach(s=>$(s).disabled=true);
}
function recompute(reset=true){
 if(reset)view=null;focusIndex=null;
 result=E.compare(getCompared(),funds,options());
 updateTotal();
 if(result.error)showError(result);
 else{
  $('#wb-partial').hidden=true;
  $('#wb-data-warning').textContent=result.partial?'已按你的选择显示较短可得区间：'+result.start+'—'+result.end+'。原请求起点为'+result.requestedStart+'，这不是完整'+periodName(period)+'成绩。':'';
  const longestGap=Math.max(...result.series.map(s=>s.metrics?.longestGap||0));
  $('#wb-sample-note').textContent=result.start+'—'+result.end+'，'+(result.dates.length-1)+'个公共净值区间；'+($('#wb-mode').value==='fixed'?'期初配置后自然漂移':'每日恢复目标比例')+'；现金假设年收益'+num(result.cashRate)+'%。净值含日常基金费用，未计个人交易/在途。'+(longestGap>10?'存在超过10天的净值间隔，年化波动仅作区间代理。':'')+' '+W.nav_end_note;
  $('#wb-start').value=result.requestedStart;$('#wb-end').value=result.end;
  $('#wb-chart-caption').textContent=result.start+' — '+result.end;
  renderMetrics();drawChart();
  ['#wb-export-csv','#wb-export-svg'].forEach(s=>$(s).disabled=false);
 }
 renderAssessment();renderEffects();
}
function renderMetrics(){
 $('#wb-metrics tbody').innerHTML=result.series.map((s,i)=>{
 const m=s.metrics;
 const recovery=m.mdd>=-1e-12?'样本无回撤':m.recovery?m.recoveryDays+'天（至'+m.recovery+'）':'截至终点未修复';
 return `<tr><td><span class="wb-line-name" style="color:${colors[i]}">${esc(s.name)}</span><div class="wb-composition">${esc(allocation(s.weights))}</div></td><td class="number">${pct(m.return)}</td><td class="number">${pct(m.mdd)}</td><td class="number">${plain(m.vol*100,2)}</td><td class="number">${pct(m.currentDrawdown)}</td><td>${recovery}</td></tr>`;
 }).join('');
}
function renderAssessment(){
 const metrics=result&&!result.error?result.series[0]?.metrics:null;
 const a=E.assess(weights,funds,$('#wb-goal').value,metrics);
 const used=Object.entries(weights).filter(([c,w])=>w>0&&c!=='CASH');
 const inputs=W.policy.macro_inputs||[];
 $('#wb-assessment').innerHTML=`<div class="wb-judgment ${a.status}"><span class="eyebrow">组合适配 / 2026.11.22研究规则</span><h3>${esc(a.verdict)}</h3><div class="wb-judge-metrics"><span>披露股权映射：${a.equity===null?'仅已知部分 '+plain(a.knownEquity):plain(a.equity)}</span><span>成长进攻类委托：${plain(a.growth||0)}</span><span>最大单基金：${plain(a.max||0)}</span></div><div class="wb-evidence-grid"><div><h4>支持与事实</h4><ul>${a.reasons.map(x=>'<li>'+esc(x)+'</li>').join('')||'<li>比例和证据不足，暂不推断。</li>'}</ul></div><div><h4>反证与需要补齐的部分</h4><ul>${a.issues.map(x=>'<li>'+esc(x)+'</li>').join('')||'<li>未触发结构提醒，不代表没有风险；共同需求、估值与流动性仍需持续核验。</li>'}</ul></div></div><details class="wb-sources"><summary>逐项基金依据、文档贡献与日期</summary>${used.map(([c,w])=>{const f=funds[c];return `<div><h4>${esc(f?.name||c)} · ${num(w)}%</h4><p>${esc(f?.role||'职责待核')}；${esc(f?.tenure||'现任阶段待核')}。${esc(f?.thesis||'缺少研究资料')}<br>反证：${esc(f?.risk||'尚未完成研究')}<br><span class="small">${esc(f?.evidence_level||'用户添加，资料待核')}；净值至${esc(f?.data_asof||'缺失')}；持仓快照${esc(f?.holdings_asof||'未核')}。</span></p>${(f?.sources||[]).map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)} ↗</a>`).join(' · ')}</div>`}).join('')}<h4>宏观与文档如何进入判断</h4>${inputs.map(x=>'<p>'+esc(x)+'</p>').join('')}<p>${esc(W.policy.threshold_note)}</p></details><p class="small">${esc(a.boundary)}未知基金净值可用于观测，不等于其事实、能力或买价已核。</p></div>`;
}
function renderEffects(){
 effects=[];
 const target=$('#wb-effects tbody'),budget=Number($('#wb-effect-weight').value),valid=!E.validateWeights(weights)&&budget>0&&budget<=50;
 if(!valid){target.innerHTML='<tr><td colspan="6">先将当前组合合计到100%，并设置1%—50%的实验预算。</td></tr>';return}
 target.innerHTML=W.focus_codes.map((c,i)=>{
  const f=funds[c],variant=E.mix(weights,c,budget);
  const r=E.compare([currentPlan(),{id:'EFFECT',name:'换入'+fundLabel(c),weights:variant}],funds,options());
  const a=E.assess(variant,funds,$('#wb-goal').value,!r.error?r.series[1].metrics:null);
  const before=E.assess(weights,funds,$('#wb-goal').value);
  const deltaEq=a.equity!==null&&before.equity!==null?a.equity-before.equity:null;
  let ret='数据不足',dd='数据不足',window='所选区间不足，不补造指标';
  if(!r.error){ret=((r.series[1].metrics.return-r.series[0].metrics.return)*100).toFixed(2);dd=((r.series[1].metrics.mdd-r.series[0].metrics.mdd)*100).toFixed(2);ret=(Number(ret)>=0?'+':'')+ret;dd=(Number(dd)>=0?'+':'')+dd;window=r.start+'—'+r.end}
  effects.push({code:c,weights:variant,comparison:r,assessment:a});
  return `<tr><td><strong>${esc(f.name)}</strong><div class="wb-effect-note">${esc(f.role)}<br>${esc(f.risk)}<br>${esc(f.focus_judgment?.ten_percent_shift||'')}<br><span class="small">${esc(window)}</span></div></td><td class="number">${ret}</td><td class="number">${dd}</td><td class="number">${deltaEq===null?'未核':(deltaEq>=0?'+':'')+deltaEq.toFixed(2)}</td><td>${esc(a.verdict)}</td><td><button type="button" data-effect="${i}">放入编辑器看曲线</button></td></tr>`;
 }).join('');
}
function valueAt(s,i){return $('#wb-chart-mode').value==='drawdown'?s.metrics.drawdown[i]:s.wealth[i]-1}
function viewBounds(){
 const n=result.dates.length;return view||{lo:0,hi:n-1};
}
function drawChart(){
 if(!result||result.error)return;
 const {lo,hi}=viewBounds();const values=result.series.flatMap(s=>result.dates.slice(lo,hi+1).map((d,j)=>valueAt(s,lo+j)));
 const small=window.innerWidth<650,axisSize=small?22:11,legendSize=small?24:12;
 let min=Math.min(0,...values),max=Math.max(0,...values);const pad=Math.max(.004,(max-min)*.12);min-=pad;max+=pad;
 const x=i=>62+(i-lo)/(hi-lo)*824,y=v=>318-(v-min)/(max-min)*246;
 result.geometry={lo,hi,min,max,x,y};
 const grid=Array.from({length:5},(_,i)=>{const v=min+(max-min)*i/4;return `<line x1="62" x2="886" y1="${y(v)}" y2="${y(v)}" stroke="#ffffff16"/><text x="50" y="${y(v)+4}" fill="#b1a797" font-size="${axisSize}" text-anchor="end">${(v*100).toFixed(1)}%</text>`}).join('');
 const dates=Array.from({length:4},(_,j)=>{const i=Math.round(lo+(hi-lo)*j/3);return `<text x="${x(i)}" y="350" fill="#a59e94" font-size="${axisSize}" text-anchor="${j===0?'start':j===3?'end':'middle'}">${result.dates[i]}</text>`}).join('');
 const paths=result.series.map((s,j)=>{const d=result.dates.slice(lo,hi+1).map((date,k)=>(k?'L':'M')+x(lo+k).toFixed(2)+','+y(valueAt(s,lo+k)).toFixed(2)).join(' ');
 return (j===0?`<path d="${d} L886,318 L62,318Z" fill="url(#wb-fill)" opacity=".55"/>`:'')+`<path d="${d}" stroke="${colors[j]}" fill="none" stroke-width="${j===0?2.8:2.1}" stroke-linejoin="round"/>`;
 }).join('');
 const legend=result.series.map((s,i)=>`<line x1="${64+(i%2)*410}" x2="${84+(i%2)*410}" y1="${22+Math.floor(i/2)*23}" y2="${22+Math.floor(i/2)*23}" stroke="${colors[i]}" stroke-width="3"/><text x="${94+(i%2)*410}" y="${26+Math.floor(i/2)*23}" fill="${colors[i]}" font-size="${legendSize}">${esc(s.name.slice(0,small?12:29))}</text>`).join('');
 $('#wb-chart').innerHTML=`<title>${esc(result.series.map(s=>s.name).join(' 与 '))}历史${$('#wb-chart-mode').value==='drawdown'?'回撤':'收益'}曲线</title><defs><linearGradient id="wb-fill" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#b88653" stop-opacity=".24"/><stop offset="1" stop-color="#b88653" stop-opacity="0"/></linearGradient></defs>${grid}${paths}${legend}${dates}<g id="wb-chart-focus"></g>`;
 $('#wb-tooltip').hidden=true;
}
function chartPosition(event){
 const svg=$('#wb-chart'),point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;const matrix=svg.getScreenCTM();return matrix?point.matrixTransform(matrix.inverse()):{x:0,y:0};
}
function hoverAt(i,event){
 if(!result||result.error)return;
 const g=result.geometry;i=Math.max(g.lo,Math.min(g.hi,i));focusIndex=i;
 const line=`<line x1="${g.x(i)}" x2="${g.x(i)}" y1="70" y2="318" stroke="#c6b8a080" stroke-dasharray="3 3"/>`;
 $('#wb-chart-focus').innerHTML=line+result.series.map((s,j)=>`<circle cx="${g.x(i)}" cy="${g.y(valueAt(s,i))}" r="3.8" fill="${colors[j]}"/>`).join('');
 const tip=$('#wb-tooltip');tip.innerHTML='<strong>'+result.dates[i]+'</strong>'+result.series.map((s,j)=>`<div class="wb-tip-row"><span style="color:${colors[j]}">${esc(s.name.slice(0,20))}</span><b>${pct(valueAt(s,i))}</b></div>`).join('');tip.hidden=false;
 const box=$('#wb-chart-area').getBoundingClientRect(),width=Math.min(260,box.width*.72);
 tip.style.width=width+'px';tip.style.left=Math.max(3,Math.min(box.width-width-8,(event?.clientX||box.left+20)-box.left+12))+'px';
}
$('#wb-chart').addEventListener('pointermove',event=>{
 if(!result||result.error)return;const p=chartPosition(event),g=result.geometry;
 if(drag){const n=result.dates.length,span=drag.hi-drag.lo,shift=Math.round((p.x-drag.x)/824*span),lo=Math.max(0,Math.min(n-1-span,drag.lo-shift));view={lo,hi:lo+span};drawChart();return}
 if(p.x>=62&&p.x<=886&&p.y>=60&&p.y<=330)hoverAt(Math.round(g.lo+(p.x-62)/824*(g.hi-g.lo)),event);
});
$('#wb-chart').addEventListener('pointerleave',()=>{if(!drag){$('#wb-tooltip').hidden=true;const f=$('#wb-chart-focus');if(f)f.innerHTML=''}});
$('#wb-chart').addEventListener('pointerdown',event=>{if(event.pointerType==='touch'||!result||result.error)return;const g=viewBounds();drag={...g,x:chartPosition(event).x};$('#wb-chart').setPointerCapture(event.pointerId)});
$('#wb-chart').addEventListener('pointerup',()=>drag=null);
$('#wb-chart').addEventListener('pointercancel',()=>drag=null);
$('#wb-chart').addEventListener('wheel',event=>{
 if(!(event.metaKey||event.ctrlKey)||!result||result.error)return;event.preventDefault();
 const g=viewBounds(),n=result.dates.length,center=g.lo+(chartPosition(event).x-62)/824*(g.hi-g.lo);
 const span=Math.max(5,Math.min(n-1,Math.round((g.hi-g.lo)*(event.deltaY>0?1.22:.82)))),lo=Math.max(0,Math.min(n-1-span,Math.round(center-span/2)));view={lo,hi:lo+span};drawChart();
},{passive:false});
function resetView(){view=null;drawChart()}
$('#wb-chart').addEventListener('dblclick',resetView);$('#wb-reset-view').addEventListener('click',resetView);
window.addEventListener('resize',()=>{if(result&&!result.error)drawChart()});
function saveState(){
 try{
  const imported=Object.fromEntries(Object.entries(funds).filter(([c,f])=>f.imported&&f.nav?.length));
  localStorage.setItem(STORE,JSON.stringify({version:1,portfolios:saved,imported}));return true;
 }catch{message('浏览器存储不可用或空间不足；请导出JSON保存，当前编辑仍可继续。');return false}
}
function resolveFund(text){
 text=text.trim();if(funds[text])return text;
 const exact=Object.keys(funds).find(c=>funds[c].name===text);if(exact)return exact;
 const matches=Object.keys(funds).filter(c=>funds[c].name.includes(text));
 if(matches.length===1)return matches[0];
 if(/^\d{6}$/.test(text)){funds[text]={code:text,name:'指定基金 '+text+'（净值与资料待导入）',nav:[],imported:true,equity_pct:null,sources:[],family:'unknown',risk:'尚未核经理、持仓与价格'};refreshList();return text}
 return null;
}
$('#wb-add').addEventListener('click',()=>{
 const text=$('#wb-fund-input').value;if(!text.trim()){message('输入基金名称或六位代码。');return}
 const code=resolveFund(text);if(!code){message('名称不明确，请从提示中选择完整名称或输入六位代码。');return}
 const w=Number($('#wb-add-weight').value);if(!(w>0&&w<100)){message('添加预算须大于0、小于100%。');return}
 if(E.validateWeights(weights)){message('先把当前组合合计到100%，再明确添加预算来源。');return}
 if(Object.keys(weights).length>=12&&!weights[code]){message('一个组合最多12项；先移除一项再添加。');return}
 if($('#wb-funding').value==='cash'){
  if((weights.CASH||0)+1e-8<w){message('外部现金不足，不能凭空投入；改用按比例腾出或修改比例。');return}
  weights.CASH-=w;weights[code]=(weights[code]||0)+w;
 }else weights=E.mix(weights,code,w);
 renderEditor();recompute();message('已明确划出'+num(w)+'%组合预算给'+fundLabel(code)+'；这是研究实验，没有执行交易。');
});
$('#wb-solo').addEventListener('click',()=>{
 const text=$('#wb-fund-input').value.trim();if(!text){message('先指定基金名称或代码。');return}
 const code=resolveFund(text);if(!code){message('名称不明确，请选完整名称或输入六位代码。');return}
 weights={[code]:100};draftName='单基金观察：'+fundLabel(code);selected=[];allowPartial=false;
 renderEditor();compareList();recompute();message('现在只观察该份额自身历史；100%是单基金研究回放，不是满仓建议。');
});
$('#wb-rows').addEventListener('input',event=>{
 const c=event.target.dataset.weight;if(!c)return;weights[c]=Number(event.target.value);updateTotal();clearTimeout(debounce);debounce=setTimeout(()=>recompute(),180);
});
$('#wb-rows').addEventListener('click',event=>{const c=event.target.closest('[data-remove]')?.dataset.remove;if(!c)return;delete weights[c];renderEditor();recompute();message('已移除，剩余比例请明确调整到100%。')});
$('#wb-normalize').addEventListener('click',()=>{
 const sum=Object.values(weights).reduce((n,x)=>n+x,0);
 if(!Number.isFinite(sum)||sum<=0||Object.values(weights).some(w=>w<0)){message('比例无效，无法按比例重置。');return}
 weights=Object.fromEntries(Object.entries(weights).map(([c,w])=>[c,w/sum*100]));renderEditor();recompute();message('已按现有相对比例合计到100%，未改变选择的基金。');
});
$('#wb-cash-rest').addEventListener('click',()=>{
 const sum=Object.entries(weights).filter(([c])=>c!=='CASH').reduce((n,[c,w])=>n+w,0);
 if(!Number.isFinite(sum)||sum>100||sum<0){message('基金比例超过100%或无效，不能将负余额当现金。');return}
 weights.CASH=100-sum;renderEditor();recompute();message('余额已明确记为外部现金。');
});
$('#wb-name').addEventListener('input',event=>{draftName=event.target.value;clearTimeout(debounce);debounce=setTimeout(()=>recompute(false),180)});
$('#wb-preset').addEventListener('change',event=>{
 const p=planByKey(event.target.value);if(!p)return;weights=clone(p.weights);draftName='编辑：'+p.name;allowPartial=false;renderEditor();recompute();message('已载入完整比例，继续修改或保存为自己的方案。');
});
$('#wb-save').addEventListener('click',()=>{
 const error=E.validateWeights(weights);if(error){message(error);return}
 const p=currentPlan(),existing=saved.findIndex(s=>s.name===p.name);
 if(existing>=0)saved[existing]=p;else{if(saved.length>=12){message('已保存12套组合，请导出后修改已有同名方案。');return}saved.push(p)}
 presetOptions();compareList();if(saveState())message('已保存在此浏览器；跨设备使用请导出JSON。');
});
$('#wb-compare-list').addEventListener('change',event=>{
 const k=event.target.value;if(event.target.checked){if(selected.length>=3){event.target.checked=false;message('同图最多我的组合＋3项对照，先取消一个。');return}selected.push(k)}else selected=selected.filter(x=>x!==k);
 allowPartial=false;recompute();
});
$('.wb-periods').addEventListener('click',event=>{
 const b=event.target.closest('[data-wb-period]');if(!b)return;period=b.dataset.wbPeriod;customDates=null;allowPartial=false;
 $('.wb-periods').querySelectorAll('button').forEach(x=>{x.classList.toggle('selected',x===b);x.setAttribute('aria-pressed',String(x===b))});recompute();
});
$('#wb-custom-period').addEventListener('click',()=>{
 customDates={start:$('#wb-start').value,end:$('#wb-end').value};allowPartial=false;
 $('.wb-periods').querySelectorAll('button').forEach(x=>{x.classList.remove('selected');x.setAttribute('aria-pressed','false')});recompute();
});
$('#wb-partial').addEventListener('click',()=>{allowPartial=true;recompute()});
['wb-mode','wb-chart-mode','wb-cash-rate','wb-goal','wb-effect-weight'].forEach(id=>$('#'+id).addEventListener('change',()=>recompute()));
$('#wb-effects').addEventListener('click',event=>{
 const button=event.target.closest('[data-effect]');if(!button)return;const effect=effects[Number(button.dataset.effect)];if(!effect)return;
 plans.EXPERIMENT_BASE=currentPlan();plans.EXPERIMENT_BASE.name='换入前：'+draftName;selected=['EXPERIMENT_BASE'];
 weights=clone(effect.weights);draftName='实验：换入'+fundLabel(effect.code);renderEditor();compareList();recompute();$('#wb-chart-area').scrollIntoView({behavior:'smooth',block:'center'});
 message('图中同时显示换入前后配置，适配判断也已更新。');
});
async function importCSV(event){
 const file=event.target.files?.[0];if(!file)return;
 try{
  if(file.size>8*1024*1024)throw Error('CSV超过8MB，请精简后导入。');
  const code=$('#wb-import-code').value.trim(),name=$('#wb-import-name').value.trim();if(!/^\d{6}$/.test(code)||!name)throw Error('先填写六位基金代码与名称，区分A/C份额。');
  const parsed=E.parseCSV(await file.text());
  const key=funds[code]&&!funds[code].imported?'IMPORTED_'+code:code;
  funds[key]={code,name:name+'（用户导入）',nav:parsed.nav,first_date:parsed.nav[0][0],data_asof:parsed.nav.at(-1)[0],nav_source:parsed.method,imported:true,equity_pct:null,family:'unknown',role:'持仓与经理职责待核',tenure:'用户指定身份，未独立认证',thesis:'仅完成数据格式核验，来源真实性和基金身份待核。',risk:'没有持仓、经理阶段与买价证据，不能给出完整适配评级。',sources:[],evidence_level:'用户提供数据，不是独立核验'};
  refreshList();$('#wb-fund-input').value=key;
  recompute();saveState();message('已导入'+parsed.nav.length+'个净值点（'+funds[key].first_date+'—'+funds[key].data_asof+'）。可点击“添加并比较”；资料不足时不冒充完整评级。');
 }catch(error){message('导入失败：'+error.message)}
 finally{event.target.value=''}
}
$('#wb-csv').addEventListener('change',importCSV);
$('#wb-json-import').addEventListener('change',async event=>{
 const file=event.target.files?.[0];if(!file)return;
 try{
  if(file.size>8*1024*1024)throw Error('文件超过8MB。');
  const data=JSON.parse(await file.text());if(data.schema!=='asymmetry-workbench-v1'||!data.portfolio||E.validateWeights(data.portfolio.weights))throw Error('不是本站有效组合导出文件。');
  for(const [k,f] of Object.entries(data.imported||{})){if(!/^(?:IMPORTED_)?\d{6}$/.test(k)||!validImported(f))throw Error('导入净值格式无效。');if(funds[k]&&!funds[k].imported)throw Error('不能覆盖内置已核数据。')}
  const newFunds={...funds,...(data.imported||{})};if(Object.keys(data.portfolio.weights).some(c=>!newFunds[c]))throw Error('组合有缺少数据的基金。');
  for(const [k,f] of Object.entries(data.imported||{}))funds[k]=importedRecord(f);
  weights=clone(data.portfolio.weights);draftName=String(data.portfolio.name||'导入组合').slice(0,70);refreshList();renderEditor();allowPartial=false;recompute();message('组合已导入；外部数据仍按用户资料处理。');
 }catch(error){message('导入失败：'+error.message)}
 finally{event.target.value=''}
});
function download(name,content,type){
 const blob=new Blob([content],{type}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$('#wb-template').addEventListener('click',()=>download('净值CSV列名模板.csv','date,wealth\n','text/csv;charset=utf-8'));
$('#wb-export-csv').addEventListener('click',()=>{
 if(!result||result.error)return;
 const quote=s=>'"'+String(s).replace(/"/g,'""')+'"';
 const lines=[['date',...result.series.map(s=>s.name+'财富指数')].map(quote).join(',')];
 const {lo,hi}=viewBounds();
 result.dates.slice(lo,hi+1).forEach((d,j)=>{const i=lo+j;lines.push([d,...result.series.map(s=>s.wealth[i].toFixed(10))].join(','))});
 download('组合同窗财富曲线.csv','\uFEFF'+lines.join('\n'),'text/csv;charset=utf-8');
});
$('#wb-export-svg').addEventListener('click',()=>{
 if(!result||result.error)return;const svg=$('#wb-chart').cloneNode(true);svg.setAttribute('xmlns','http://www.w3.org/2000/svg');svg.setAttribute('style','background:#101111');svg.querySelector('#wb-chart-focus')?.remove();
 download('组合曲线.svg',new XMLSerializer().serializeToString(svg),'image/svg+xml;charset=utf-8');
});
$('#wb-export-json').addEventListener('click',()=>{
 const p=currentPlan();if(E.validateWeights(p.weights)){message('先使比例有效，再导出组合。');return}
 const imported=Object.fromEntries(Object.entries(funds).filter(([c,f])=>f.imported&&p.weights[c]>0&&f.nav?.length));
 const assessment=E.assess(weights,funds,$('#wb-goal').value,result&&!result.error?result.series[0].metrics:null);
 const output={schema:'asymmetry-workbench-v1',exported_at:new Date().toISOString(),research_baseline:W.date,portfolio:p,options:options(),goal:$('#wb-goal').value,assessment,imported,chart_view:result&&!result.error?{start:result.dates[viewBounds().lo],end:result.dates[viewBounds().hi]}:null,
  result:result&&!result.error?{start:result.start,end:result.end,requestedStart:result.requestedStart,partial:result.partial,metrics:result.series.map(s=>({name:s.name,weights:s.weights,metrics:s.metrics,riskContribution:s.riskContribution}))}:{error:result?.error}};
 download('我的组合研究.json',JSON.stringify(output,null,2),'application/json;charset=utf-8');
});
presetOptions();refreshList();renderEditor();compareList();recompute();
window.WorkbenchApp={getSnapshot:()=>({weights:clone(weights),result:clone(result),assessment:E.assess(weights,funds,$('#wb-goal').value,result&&!result.error?result.series[0].metrics:null)})};
})();
