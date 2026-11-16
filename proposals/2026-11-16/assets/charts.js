(function () {
  const {analysis:X,weekly:W}=window.REVIEW_DATA;
  const style=getComputedStyle(document.documentElement);
  const color=k=>style.getPropertyValue(k).trim();
  const accent=color('--accent'),accent2=color('--accent2'),down=color('--down'),muted=color('--muted'),rule=color('--rule');
  const axis={nameTextStyle:{color:muted},axisLabel:{color:muted},axisLine:{lineStyle:{color:rule}},splitLine:{lineStyle:{color:rule}}};
  const charts=['fund-chart','audit-chart','scenario-chart'].map(id=>echarts.init(document.getElementById(id),null,{renderer:'svg'}));
  const short={'011370':'华商均衡','002244':'低碳科技','022714':'万家新兴蓝筹','010390':'科益','021180':'产业机遇','022415':'前海国企','021902':'广发主题'};
  const tooltip={trigger:'axis',appendToBody:true,valueFormatter:v=>(+v).toFixed(2)+'%'};
  function render(){
    const field=document.getElementById('window').value,rows=W.funds.filter(p=>short[p.code]);
    charts[0].setOption({animation:false,tooltip,grid:{left:110,right:30,top:25,bottom:50},
      xAxis:{...axis,type:'value',name:'收益 %',nameLocation:'middle',nameGap:28},
      yAxis:{...axis,type:'category',inverse:true,data:rows.map(p=>short[p.code])},
      series:[{type:'bar',data:rows.map(p=>({value:+(100*p[field]).toFixed(2),itemStyle:{color:p[field]>=0?accent:down}}))}]},true);
    const audit=W.audits[+document.getElementById('audit').value];
    const first=audit.variants.find(r=>r.execution==='first_only'&&r.fee===.005&&r.delay===1);
    const both=audit.variants.find(r=>r.execution==='both'&&r.fee===.005&&r.delay===1);
    charts[1].setOption({animation:false,tooltip,legend:{textStyle:{color:muted}},grid:{left:45,right:25,top:45,bottom:50},
      xAxis:{...axis,type:'category',data:audit.dates},yAxis:{...axis,type:'value',name:'累计 %'},
      series:[['保持',audit.hold.path,accent2],['首批',first.path,down],['两批',both.path,accent]].map(([name,data,c])=>({name,type:'line',showSymbol:true,data:data.map(v=>v*100),itemStyle:{color:c}}))},true);
    document.getElementById('audit-detail').textContent=`${audit.start}—${audit.end}，${audit.intervals}个共同区间。图中低碳费率0.5%，转入延迟1个交易日。${audit.status}；不代表用户成交。`;
    const inv=document.getElementById('inventory').value;
    charts[2].setOption({animation:false,tooltip,legend:{textStyle:{color:muted}},grid:{left:112,right:25,top:45,bottom:50},
      xAxis:{...axis,type:'value',name:'条件均值 %',nameLocation:'middle',nameGap:30},
      yAxis:{...axis,type:'category',inverse:true,data:['震荡分化','科技盈利修复','增长担忧','实际利率上行']},
      series:['hold','second'].map((k,i)=>({name:i?'两批完成':'保持原结构',type:'bar',itemStyle:{color:i?accent:accent2},data:X.model.branches.map(b=>+(b.response[inv+'_'+k].mean*100).toFixed(2))}))},true);
    const rates=X.model.branches.find(b=>b.id==='rates').response;
    document.getElementById('scenario-detail').textContent=`利率压力分支最弱10%路径均值：原结构${(rates[inv+'_hold'].es10*100).toFixed(1)}%，两批完成${(rates[inv+'_second'].es10*100).toFixed(1)}%。不是未来置信区间或损失上限。`;
  }
  document.getElementById('execution').addEventListener('change',ev=>document.querySelectorAll('.action').forEach(el=>el.hidden=ev.target.value!=='all'&&el.dataset.state!==ev.target.value));
  ['window','audit','inventory'].forEach(id=>document.getElementById(id).addEventListener('change',render));
  window.addEventListener('resize',()=>charts.forEach(c=>c.resize()));
  render();window.WEEKLY_REVIEW_READY=true;
})();
