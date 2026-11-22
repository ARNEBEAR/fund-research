/* Pure portfolio accounting and disclosed research screening, shared with verification. */
(function(root){
'use strict';
const DAY=86400000;
function day(s){return Date.parse(s+'T00:00:00Z')}
function iso(t){return new Date(t).toISOString().slice(0,10)}
function validDate(s){return /^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(day(s))&&iso(day(s))===s}
function monthsBefore(s,n){const d=new Date(day(s)),y=d.getUTCFullYear(),m=d.getUTCMonth()-n,date=d.getUTCDate();const last=new Date(Date.UTC(y,m+1,0)).getUTCDate();return iso(Date.UTC(y,m,Math.min(date,last)))}
function validateWeights(weights){
 const entries=Object.entries(weights||{});if(!entries.length)return '至少添加一项基金或现金。';
 if(entries.some(([c,w])=>!c||!Number.isFinite(w)||w<0||w>100))return '比例必须是0—100之间的有效数字。';
 const sum=entries.reduce((n,[c,w])=>n+w,0);return Math.abs(sum-100)>0.005?'当前合计'+sum.toFixed(2)+'%，请明确调至100%；不会自动借款或补现金。':null;
}
function mix(weights,code,pct){
 if(!Number.isFinite(pct)||pct<=0||pct>=100)throw Error('换入比例须在0—100%之间。');
 const r={};for(const [c,w] of Object.entries(weights))if(w>0)r[c]=w*(1-pct/100);
 r[code]=(r[code]||0)+pct;return r;
}
function stats(wealth,dates){
 if(wealth.length<3)return null;
 const r=[];let peak=wealth[0],worst=0,worstI=0,peakI=0,worstPeak=0,lastPeak=0,sumdd=0,under=0,longest=0,run=0;
 for(let i=0;i<wealth.length;i++){
   if(i)r.push(wealth[i]/wealth[i-1]-1);
   if(wealth[i]>=peak-1e-12){peak=wealth[i];peakI=i;lastPeak=i}
   const dd=wealth[i]/peak-1;sumdd+=dd*dd;
   if(dd<worst){worst=dd;worstI=i;worstPeak=peakI}
   if(i&&dd<-1e-10){under++;run++;longest=Math.max(longest,run)}else run=0;
 }
 const mean=r.reduce((a,b)=>a+b,0)/r.length,variance=r.reduce((a,b)=>a+(b-mean)**2,0)/(r.length-1);
 let recovered=null;if(worst<0){for(let i=worstI+1;i<wealth.length;i++)if(wealth[i]>=wealth[worstPeak]-1e-12){recovered=i;break}}
 const high=[];let h=wealth[0];for(const v of wealth){h=Math.max(h,v);high.push(v/h-1)}
 let longestGap=0;for(let i=1;i<dates.length;i++)longestGap=Math.max(longestGap,(day(dates[i])-day(dates[i-1]))/DAY);
 return {return:wealth.at(-1)-1,mdd:worst,vol:Math.sqrt(variance*252),ulcer:Math.sqrt(sumdd/wealth.length),
  currentDrawdown:wealth.at(-1)/peak-1,underwater:under/r.length,longestUnderwater:longest,
  currentUnderwaterDays:Math.round((day(dates.at(-1))-day(dates[lastPeak]))/DAY),
  peak:dates[worstPeak],trough:dates[worstI],recovery:recovered===null?null:dates[recovered],
  recoveryDays:recovered===null?null:Math.round((day(dates[recovered])-day(dates[worstPeak]))/DAY),
  drawdown:high,intervals:r.length,longestGap};
}
function covarianceContribution(grid,weights,maps){
 const codes=Object.keys(weights).filter(c=>c!=='CASH'&&weights[c]>0);if(!codes.length)return {};
 const dates=grid.slice(-61),returns=codes.map(c=>dates.slice(1).map((d,i)=>maps[c].get(d)/maps[c].get(dates[i])-1));
 if(dates.length<4)return {};
 const means=returns.map(a=>a.reduce((n,x)=>n+x,0)/a.length),cov=returns.map((a,i)=>returns.map((b,j)=>a.reduce((n,x,k)=>n+(x-means[i])*(b[k]-means[j]),0)/(a.length-1)));
 const w=codes.map(c=>weights[c]/100),cw=cov.map(row=>row.reduce((n,x,i)=>n+x*w[i],0)),variance=w.reduce((n,x,i)=>n+x*cw[i],0);
 return variance>1e-15?Object.fromEntries(codes.map((c,i)=>[c,w[i]*cw[i]/variance])):{};
}
function compare(portfolios,funds,options={}){
 for(const p of portfolios){const error=validateWeights(p.weights);if(error)return {error,kind:'weights',portfolio:p.name}}
 const codes=[...new Set(portfolios.flatMap(p=>Object.entries(p.weights).filter(([c,w])=>w>0&&c!=='CASH').map(([c])=>c)))];
 const unavailable=codes.filter(c=>!funds[c]?.nav?.length);
 if(unavailable.length)return {error:'缺少以下基金的净值：'+unavailable.map(c=>funds[c]?.name||c).join('、')+'。请导入数据后再计算。',kind:'missing',missing:unavailable};
 const used=codes.length?codes:['510300'];if(!funds[used[0]]?.nav?.length)return {error:'没有可用净值日期。',kind:'missing'};
 const maps=Object.fromEntries(used.map(c=>[c,new Map(funds[c].nav)]));
 const common=funds[used[0]].nav.map(x=>x[0]).filter(d=>used.every(c=>maps[c].has(d))).sort();
 if(common.length<3)return {error:'各基金净值没有足够共同日期，无法比较；不会把缺失日收益填为0。',kind:'dates'};
 const last=common.at(-1);let end=options.end||last;
 if(!validDate(end))return {error:'结束日期无效。',kind:'dates'};
 const available=common.filter(d=>d<=end);if(available.length<3)return {error:'指定结束日前没有足够共同净值。',kind:'dates'};
 end=available.at(-1);
 const periods={'1M':1,'3M':3,'6M':6,'1Y':12,'2Y':24};
 let requestedStart=options.start||(options.period==='ALL'?available[0]:monthsBefore(end,periods[options.period]||3));
 if(!validDate(requestedStart)||requestedStart>=end)return {error:'起止日期无效，请选择开始早于结束的日期。',kind:'dates'};
 const shortages=used.filter(c=>funds[c].nav[0][0]>requestedStart).map(c=>({code:c,name:funds[c].name,first:funds[c].nav[0][0]}));
 const periodName={'1M':'一个月','3M':'三个月','6M':'六个月','1Y':'一年','2Y':'两年','ALL':'全部可得'}[options.period]||'自定义';
 if(shortages.length&&!options.allowPartial)return {error:'所选区间数据不足：'+shortages.map(x=>x.name+'始于'+x.first).join('；')+'。不能把较短样本当作完整'+periodName+'区间。',kind:'short',shortages,requestedStart,end};
 const anchors=available.filter(d=>d<=requestedStart);
 const actualStart=anchors.length?anchors.at(-1):available[0];
 const grid=available.filter(d=>d>=actualStart);
 if(grid.length<3)return {error:'区间仅有'+grid.length+'个共同净值点，不能计算有效曲线与波动。',kind:'dates'};
 const cashRate=Number(options.cashRate||0)/100;
 if(!Number.isFinite(cashRate)||cashRate<=-1||cashRate>.2)return {error:'现金年收益假设无效。',kind:'weights'};
 const cash=grid.map(d=>(1+cashRate)**((day(d)-day(grid[0]))/DAY));
 const series=portfolios.map(p=>{
  const w=p.weights;let wealth;
  if(options.mode==='daily'){
    wealth=[1];
    for(let i=1;i<grid.length;i++){
      let r=(cash[i]/cash[i-1]-1)*(w.CASH||0)/100;
      for(const c of codes)if(w[c]>0)r+=(maps[c].get(grid[i])/maps[c].get(grid[i-1])-1)*w[c]/100;
      wealth.push(wealth.at(-1)*(1+r));
    }
  }else wealth=grid.map((d,i)=>{
      let v=cash[i]*(w.CASH||0)/100;
      for(const c of codes)if(w[c]>0)v+=maps[c].get(d)/maps[c].get(grid[0])*w[c]/100;
      return v;
  });
  return {...p,wealth,metrics:stats(wealth,grid),riskContribution:covarianceContribution(grid,w,maps)};
 });
 return {dates:grid,start:grid[0],end,requestedStart,partial:shortages.length>0||grid[0]>requestedStart,
  shortages,series,mode:options.mode||'fixed',cashRate:cashRate*100,allFundCodes:codes,
  note:'所有曲线按同一公共净值日期交集；'+grid.length+'个净值点。'};
}
function assess(weights,funds,goal='smooth',metrics=null){
 const error=validateWeights(weights);if(error)return {verdict:'比例无效，暂不评级',status:'insufficient',issues:[error],reasons:[]};
 const entries=Object.entries(weights).filter(([c,w])=>w>0),equityEntries=entries.filter(([c])=>c!=='CASH');
 const unknown=equityEntries.filter(([c])=>!funds[c]||funds[c].imported||funds[c].equity_pct===null||funds[c].equity_pct===undefined);
 let eq=0,growth=0,resource=0;
 const growthTypes=['growth','global_technology','manufacturing_growth'];
 for(const [c,w] of equityEntries){const f=funds[c];if(!f)continue;if(Number.isFinite(f.equity_pct))eq+=w*f.equity_pct/100;if(growthTypes.includes(f.family))growth+=w;if(['resource_rotation','value','flexible_value'].includes(f.family))resource+=w}
 const max=Math.max(0,...equityEntries.map(([c,w])=>w)),issues=[],reasons=[];
 let bad=false;
 if(max>(goal==='growth'?50:35)){issues.push('单只基金占'+max.toFixed(1)+'%，高于本工具的'+(goal==='growth'?50:35)+'%集中度提醒线；失败可能被同一经理和持仓主导。');bad=true}
 if(goal!=='growth'&&growth>35){issues.push('成长/科技/制造进攻类委托合计'+growth.toFixed(1)+'%，超过平滑目标的35%提醒线。这是基金预算分组，不是穿透科技持股占比。');bad=true}
 if(goal==='defense'&&eq>60){issues.push('已知披露股权映射约'+eq.toFixed(1)+'%，与低回撤优先目标不匹配；优秀经理不能替代总风险控制。');bad=true}
 else if(goal==='smooth'&&eq>85){issues.push('披露股权映射约'+eq.toFixed(1)+'%，超过85%权益强度提醒线；共同市场冲击可能明显破坏平滑目标。');bad=true}
 if(resource>45)issues.push('价值、资源轮动与灵活价值委托合计'+resource.toFixed(1)+'%；这些基金可能共享金融、资源和国内需求，行业名字不同也需要检查共同损失。');
 if((weights['010390']||0)>0)issues.push('科益有AI细分与平台研究，但独管自2026.05、容量变化尚待检验；不是成熟稳定核心的已证替代。');
 if((weights['027170']||0)>0)issues.push('交银环球C历史短，蔡铮自2026.10独管；与美股大盘高联动，海外席位不自动创造风险分散。');
 if((weights.CASH||0)>40&&goal!=='defense'){issues.push('外部现金超过40%，保护短期可用性但降低权益参与，不应直接作为长期增值目标的永久方案。');bad=true}
 if(!equityEntries.length&&goal!=='defense'){issues.push('全现金结构没有权益增长来源，与本次长期权益目标不适配。');bad=true}
 if(unknown.length)issues.push('以下基金缺少已核持仓/经理资料：'+unknown.map(([c])=>funds[c]?.name||c).join('、')+'。用户导入净值不能补齐这些证据。');
 if(equityEntries.length>1)reasons.push('包含'+equityEntries.length+'项基金委托；数量只降低单项预算，不能单独证明分散。');
 if((weights['011066']||0)>0)reasons.push('高鑫提供企业质量与买价机制，制造/出口及集中风险仍在；长期A/C总成本需核。');
 if((weights['021902']||0)>0)reasons.push('广发提供估值克制与可变权益强度，收费和踏空代价要一起评价；不等同外部现金。');
 reasons.push('股权快照截至2026.09.30；最新净值和旧披露不是同一时点。需求、信用、财政与实际利率仍决定总风险和买价。');
 if(metrics)reasons.push('所选共同窗口收益'+(metrics.return*100).toFixed(2)+'%、最大回撤'+(metrics.mdd*100).toFixed(2)+'%；'+(metrics.recovery?'最大回撤已在样本中修复':'最大回撤截至终点未修复')+'。这只检验样本，不当作未来适配胜率。');
 return {verdict:unknown.length?'信息不足，暂不作完整评级':bad?(goal==='growth'?'集中风险偏高，不宜作为唯一成长组合':'不适合以'+(goal==='defense'?'低回撤':'平滑')+'为首要目标的默认组合'):'有条件适配'+(goal==='growth'?'成长参与':'长期权益委托')+'，仍需持续验证',
   status:unknown.length?'insufficient':bad?'poor':'conditional',equity:unknown.length?null:eq,knownEquity:eq,growth,resource,max,issues,reasons,
   boundary:'此为有日期的研究规则判断，未实时人工审议新组合，不是经理评分、市场胜率或回撤承诺。'};
}
function parseCSV(text){
 const lines=text.replace(/^\uFEFF/,'').trim().split(/\r?\n/).filter(x=>x.trim());
 if(lines.length<4)throw Error('至少需要表头与三个净值点。');
 const split=s=>{const vals=[];let v='',quoted=false;for(let i=0;i<s.length;i++){const c=s[i];if(c==='"'){if(quoted&&s[i+1]==='"'){v+='"';i++}else quoted=!quoted}else if(c===','&&!quoted){vals.push(v.trim());v=''}else v+=c}if(quoted)throw Error('CSV引号未闭合。');vals.push(v.trim());return vals};
 const header=split(lines[0]).map(x=>x.toLowerCase()),index=names=>header.findIndex(x=>names.includes(x));
 const di=index(['date','日期','净值日期']),wi=index(['wealth','total_return_nav','复权净值','财富指数']),ui=index(['unit_nav','nav','单位净值']),ci=index(['cumulative_nav','累计净值']);
 if(di<0||(wi<0&&(ui<0||ci<0)))throw Error('需要date,wealth（复权净值），或date,unit_nav,cumulative_nav。只有单位净值不能确认分红回报。');
 const records=lines.slice(1).map((line,n)=>{const v=split(line),date=v[di];if(!validDate(date))throw Error('第'+(n+2)+'行日期无效（须YYYY-MM-DD）。');
  if(date>iso(Date.now()))throw Error('第'+(n+2)+'行日期在未来，不能当作历史正式净值。');
  const number=i=>{const x=Number(v[i]);if(!v[i]||!Number.isFinite(x)||x<=0)throw Error('第'+(n+2)+'行净值须为正数。');return x};
  return {date,wealth:wi>=0?number(wi):null,unit:ui>=0?number(ui):null,cumulative:ci>=0?number(ci):null};
 }).sort((a,b)=>a.date.localeCompare(b.date));
 if(records.some((r,i)=>i&&r.date===records[i-1].date))throw Error('有重复净值日期，请先核对重复记录。');
 if(records.length>30000)throw Error('净值点超过30000，拆分或精简后导入。');
 let w=1;const nav=records.map((r,i)=>{
   if(wi>=0)return [r.date,r.wealth/records[0].wealth];
   if(i){const p=records[i-1],increment=(r.cumulative-r.unit)-(p.cumulative-p.unit);
    if(increment<-.0002)throw Error('累计与单位净值差额下降，可能有拆分或更正；请导入核实的复权wealth序列。');
    w*=(r.unit+Math.max(0,increment))/p.unit;
   }return [r.date,w];
 });
 if(nav.some((r,i)=>!Number.isFinite(r[1])||r[1]<=0||(i&&Math.abs(r[1]/nav[i-1][1]-1)>1)))throw Error('存在异常净值跳变或无效财富指数，需先核分红、拆分和单位。');
 return {nav,method:wi>=0?'用户提供的复权财富序列，未独立认证':'单位＋累计净值差额识别分红并再投资；拆分更正须另核'};
}
const api={day,iso,validDate,monthsBefore,validateWeights,mix,stats,compare,assess,parseCSV};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
root.PortfolioEngine=api;
})(typeof window!=='undefined'?window:globalThis);
