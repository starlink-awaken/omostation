/* 织星驾驶舱 · metrics 板块 —— 全部序列来自真实日志
   数据来源: D.panel_history (refresh.jsonl / resident-heartbeat / agent-tick 派生)
             D.panel_events  (事件分面与时序)
             D.metrics_kpi   (health.yaml 健康分)
   红线: 不得使用 Math.random / 合成波形；无数据时显示 NOT_PROVEN/NO DATA 而非补零曲线。 */
function zxMState(){ if(!window.__zxM) window.__zxM={range:'24h',sort:'activity',hidden:{}}; return window.__zxM; }
function zxMEsc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

/* 每个范围 → 真实序列键映射（键必须存在于 panel_history / panel_events） */
function zxMSeriesFor(range){
  var D=zxData();
  var h=(D.panel_history||{}).series||{};
  var es=((D.panel_events||{}).series)||{};
  if(range==='24h') return [
    {key:'events_hourly',  label:'事件/时',   color:'#3a64b3', points:(es.hourly_24h||[]), src:'事件源聚合'},
    {key:'heartbeat_ok',   label:'心跳 OK',   color:'#10b981', points:((h.heartbeat_ok_hourly||{}).points||[]), src:'resident-heartbeat'},
    {key:'tick_ok',        label:'Tick OK',   color:'#8b5cf6', points:((h.tick_ok_hourly||{}).points||[]), src:'agent-tick-daemon'}
  ];
  if(range==='7d') return [
    {key:'events_daily',   label:'事件/日',   color:'#3a64b3', points:(es.daily_7d||[]), src:'事件源聚合'},
    {key:'refresh_ok',     label:'刷新成功',  color:'#10b981', points:((h.refresh_ok_daily||{}).points||[]).slice(-7), src:'refresh.jsonl'},
    {key:'refresh_failed', label:'刷新失败',  color:'#ef4444', points:((h.refresh_failed_daily||{}).points||[]), src:'refresh.jsonl'}
  ];
  return [
    {key:'events_daily',  label:'事件/日',  color:'#3a64b3', points:(es.daily_30d||[]), src:'事件源聚合'},
    {key:'graph_nodes',   label:'知识节点', color:'#8b5cf6', points:((h.graph_nodes_daily||{}).points||[]), src:'refresh.jsonl·strategic'},
    {key:'refresh_ok',    label:'刷新成功', color:'#10b981', points:((h.refresh_ok_daily||{}).points||[]), src:'refresh.jsonl'}
  ];
}

function zxMSpark(points,color){
  if(!points||points.length<2) return '';
  var vals=points.map(function(p){return p[1]||0});
  var mx=Math.max.apply(null,vals), mn=Math.min.apply(null,vals);
  var w=100,hh=26,rng=(mx-mn)||1;
  var d=vals.map(function(v,i){
    var x=(i/(vals.length-1))*w, y=hh-2-((v-mn)/rng)*(hh-8);
    return (i?'L':'M')+x.toFixed(1)+' '+y.toFixed(1);
  }).join(' ');
  return '<svg viewBox="0 0 '+w+' '+hh+'" preserveAspectRatio="none"><path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="1.4"/></svg>';
}

/* 环比: 与相邻等长窗口真实比较; 无基线 → null（显示「—」而不是 0%） */
function zxMDelta(points){
  var p=(points||[]).filter(function(x){return x&&x.length===2});
  if(p.length<4) return null;
  var half=Math.floor(p.length/2);
  var a=p.slice(0,half), b=p.slice(half);
  var sa=a.reduce(function(s,x){return s+x[1]},0), sb=b.reduce(function(s,x){return s+x[1]},0);
  if(!sa) return null;
  return Math.round((sb-sa)/sa*1000)/10;
}

function zxMTrendChart(datasets, hidden){
  var shown=datasets.filter(function(d){return !hidden[d.key] && d.points && d.points.length;});
  if(!shown.length) return '<div class="zx-nodata"><span class="zx-state">NO DATA</span><br>所选序列在真实日志中暂无数据</div>';
  var w=760,h=230,pl=44,pr=10,pt=12,pb=26;
  var n=Math.max.apply(null,shown.map(function(d){return d.points.length}));
  var mx=0; shown.forEach(function(d){ d.points.forEach(function(p){ if(p[1]>mx) mx=p[1]; }); });
  if(mx<=0) return '<div class="zx-nodata"><span class="zx-state">ZERO</span><br>真实序列在窗口内全为 0（未伪造曲线）</div>';
  var X=function(i){ return pl+(i/Math.max(1,n-1))*(w-pl-pr); };
  var Y=function(v){ return h-pb-(v/mx)*(h-pt-pb); };
  var grid='';
  for(var g=0;g<=4;g++){
    var v=mx*g/4, y=Y(v);
    grid+='<line x1="'+pl+'" y1="'+y.toFixed(1)+'" x2="'+(w-pr)+'" y2="'+y.toFixed(1)+'" stroke="#eef2f7"/>'+
          '<text x="'+(pl-6)+'" y="'+(y+3).toFixed(1)+'" font-size="9" fill="#9aabbd" text-anchor="end">'+(Math.round(v*10)/10)+'</text>';
  }
  var lines=shown.map(function(d){
    var path=d.points.map(function(p,i){ return (i?'L':'M')+X(i).toFixed(1)+' '+Y(p[1]).toFixed(1); }).join(' ');
    var dots=d.points.map(function(p,i){
      return '<circle cx="'+X(i).toFixed(1)+'" cy="'+Y(p[1]).toFixed(1)+'" r="2.4" fill="'+d.color+'"><title>'+
        zxMEsc(p[0])+' · '+d.label+': '+p[1]+'</title></circle>';
    }).join('');
    return '<path d="'+path+'" fill="none" stroke="'+d.color+'" stroke-width="1.8"/>'+dots;
  }).join('');
  var base=shown[0].points, ticks='';
  var step=Math.max(1,Math.ceil(n/6));
  for(var i=0;i<n;i+=step){
    var lbl=(base[i]&&base[i][0]?base[i][0].slice(5,10):'');
    ticks+='<text x="'+X(i).toFixed(1)+'" y="'+(h-8)+'" font-size="9" fill="#9aabbd" text-anchor="middle">'+lbl+'</text>';
  }
  return '<svg viewBox="0 0 '+w+' '+h+'" style="width:100%;height:auto;display:block">'+grid+lines+ticks+'</svg>';
}

function zxRenderMetrics(){
  try{
    var D=zxData();
    var kpi=D.metrics_kpi||{}, hist=D.panel_history||{}, ev=D.panel_events||{};
    var st=zxMState();
    var host=document.getElementById('zx-m-kpis'); if(!host) return;

    var fresh=document.getElementById('zx-m-fresh');
    if(fresh && typeof freshnessIndicator==='function') fresh.innerHTML=freshnessIndicator(D.observed_at||D.generated_at);

    var hs=hist.series||{}, es=ev.series||{};
    var cov=hist.coverage||{};

    /* ── KPI: 数值 + 单位 + 真实 sparkline + 真实环比 ── */
    var cards=[
      {v:kpi.total_events_24h||0,u:'',l:'24h 事件',pts:es.hourly_24h,c:'#3a64b3'},
      {v:kpi.events_per_hour_24h||0,u:'/h',l:'事件速率',pts:es.hourly_24h,c:'#2e7e79'},
      {v:(kpi.failure_rate_24h==null?'—':kpi.failure_rate_24h),u:kpi.failure_rate_24h==null?'':'%',l:'失败/阻塞率',pts:((hs.heartbeat_degraded_hourly||{}).points),c:'#ef4444'},
      {v:(kpi.health_score==null?'—':kpi.health_score),u:'',l:'健康总分',pts:null,c:'#10b981'},
      {v:((hs.tick_ok_hourly||{}).points?((hs.tick_ok_hourly||{}).points).reduce(function(s,p){return s+p[1]},0):0),u:'',l:'24h Tick 成功',pts:((hs.tick_ok_hourly||{}).points),c:'#8b5cf6'},
      {v:(kpi.sources_live||0),u:'/'+((kpi.sources_live||0)+(kpi.sources_missing||0)),l:'存活事件源',pts:null,c:'#2e7e79'}
    ];
    host.innerHTML=cards.map(function(c){
      var d=zxMDelta(c.pts);
      var dcls=d==null?'flat':(d>0?'up':'down');
      var dtxt=d==null?'环比 —':(d>0?'▲ +':'▼ ')+d+'%';
      return '<div class="zx-m-kpi"><div class="zx-m-top"><div>'+
        '<div class="zx-m-v">'+c.v+'<span class="zx-m-u">'+c.u+'</span></div>'+
        '<div class="zx-m-l">'+c.l+'</div></div>'+
        '<span class="zx-m-d '+dcls+'" title="与相邻等长窗口的真实比较">'+dtxt+'</span></div>'+
        '<div class="zx-m-spark">'+zxMSpark(c.pts,c.c)+'</div></div>';
    }).join('');

    /* ── 五维雷达（health.yaml 真实分） ── */
    var radar=document.getElementById('zx-m-radar');
    if(radar){
      var dims=[['保鲜',kpi.freshness_score,'#10b981'],['时效',kpi.staleness_score,'#8b5cf6'],
                ['漂移',kpi.drift_score,'#f59e0b'],['对齐',kpi.alignment_score,'#3a64b3'],['治理',kpi.health_score,'#ef4444']];
      var known=dims.filter(function(x){return x[1]!=null});
      if(!known.length){
        radar.innerHTML='<div class="zx-nodata"><span class="zx-state">NO DATA</span><br>health.yaml 未提供五维分值</div>';
      } else {
        var cx=120,cy=118,r=88,angles=dims.map(function(_,i){return (i*72-90)*Math.PI/180});
        var rings='';
        for(var lv=1;lv<=5;lv++){
          var rr=r*lv/5;
          rings+='<polygon points="'+angles.map(function(a){return (cx+Math.cos(a)*rr).toFixed(1)+','+(cy+Math.sin(a)*rr).toFixed(1)}).join(' ')+'" fill="none" stroke="#eef2f7"/>';
        }
        var pts=dims.map(function(d,i){ var v=(d[1]||0)/100*r; return (cx+Math.cos(angles[i])*v).toFixed(1)+','+(cy+Math.sin(angles[i])*v).toFixed(1); }).join(' ');
        var labels=dims.map(function(d,i){
          var x=cx+Math.cos(angles[i])*(r+16), y=cy+Math.sin(angles[i])*(r+16);
          return '<text x="'+x.toFixed(1)+'" y="'+(y+3).toFixed(1)+'" font-size="10" fill="#7a8fa3" text-anchor="middle">'+d[0]+'</text>';
        }).join('');
        radar.innerHTML='<svg width="240" height="240" viewBox="0 0 240 240">'+rings+labels+
          '<polygon points="'+pts+'" fill="rgba(58,100,179,.18)" stroke="#3a64b3" stroke-width="1.8"/></svg>';
        var lg=document.getElementById('zx-m-radar-legend');
        if(lg) lg.innerHTML='<div class="zx-legend">'+dims.map(function(d){
          return '<span><i style="background:'+d[2]+'"></i>'+d[0]+' '+
            (d[1]==null?'<b style="color:#c33">UNKNOWN</b>':d[1])+'</span>';
        }).join('')+'</div>';
      }
    }

    /* ── 来源分布（真实 24h 窗口 + 缺失源显式标注） ── */
    var srcs=(ev.sources||[]), sd=document.getElementById('zx-m-sources');
    if(sd){
      var live=srcs.filter(function(s){return s.state!=='MISSING'});
      var mx=Math.max.apply(null,live.map(function(s){return s.window_count||0}).concat([1]));
      sd.innerHTML=live.length?live.map(function(s){
        var v=s.window_count||0, pct=Math.round(v/mx*100);
        var col=s.state==='OK'?'#3a64b3':(s.state==='STALE'?'#f59e0b':'#94a3b8');
        return '<div class="zx-bar-row" style="margin-bottom:7px"><div class="zx-bar-head"><span>'+zxMEsc(s.label)+
          ' <span class="zx-chip '+(s.state==='OK'?'ok':s.state==='STALE'?'warn':'dim')+'">'+s.state+'</span></span>'+
          '<span>'+v+' / 累计 '+(s.total_count==null?'—':s.total_count)+'</span></div>'+
          '<div class="zx-bar-track"><i style="width:'+pct+'%;background:'+col+'"></i></div></div>';
      }).join(''):'<div class="zx-nodata">无事件源</div>';
      var note=document.getElementById('zx-m-src-note');
      var missing=srcs.filter(function(s){return s.state==='MISSING'});
      if(note) note.innerHTML=missing.length
        ? '⚠️ '+missing.length+' 个已声明源在文件系统中不存在（未接线）：<code>'+
          missing.map(function(s){return zxMEsc(s.name)}).join(', ')+'</code> —— 不计入上图，也不当 0 混入统计。'
        : '全部已声明源均存在。';
    }

    /* ── 趋势：真实序列 + 范围切换 + 首屏自动绘制 ── */
    var rl=document.getElementById('zx-m-ranges');
    if(rl && !rl.__zxWired){
      rl.__zxWired=1;
      rl.innerHTML=['24h','7d','30d'].map(function(r){
        return '<button type="button" data-r="'+r+'" onclick="zxMSetRange(\''+r+'\')">'+r+'</button>';
      }).join('');
    }
    if(rl) Array.prototype.forEach.call(rl.querySelectorAll('button'),function(b){
      b.classList.toggle('active',b.getAttribute('data-r')===st.range);
    });
    var chip=document.getElementById('zx-m-range-chip');
    if(chip) chip.textContent=st.range+' · '+(ev.summary?ev.summary.events_24h:0)+' 事件(24h)';

    var ds=zxMSeriesFor(st.range);
    var trend=document.getElementById('zx-m-trend');
    if(trend) trend.innerHTML=zxMTrendChart(ds,st.hidden);

    var lg2=document.getElementById('zx-m-legend');
    if(lg2) lg2.innerHTML=ds.map(function(d){
      var n=(d.points||[]).length;
      return '<label><input type="checkbox" '+(st.hidden[d.key]?'':'checked')+' onchange="zxMToggleSeries(\''+d.key+'\')">'+
        '<i style="background:'+d.color+'"></i>'+zxMEsc(d.label)+
        '<span style="color:#9aabbd">（'+(n?n+' 点·'+zxMEsc(d.src):'无数据')+'）</span></label>';
    }).join('');

    var covEl=document.getElementById('zx-m-coverage');
    if(covEl){
      var parts=Object.keys(cov).map(function(k){
        return zxMEsc(k)+' <code>'+zxMEsc(cov[k].path)+'</code> · '+cov[k].lines+' 行';
      });
      covEl.innerHTML=parts.length?('真实数据底座：'+parts.join('；')):'真实数据底座：未发现任何历史日志（序列将显示 NO DATA）';
    }

    /* ── Agent 效率矩阵（真实字段） ── */
    var tb=document.getElementById('zx-m-matrix');
    if(tb){
      var agents=(D.agents||[]).slice();
      var byAgent=((ev.facets||{}).by_agent)||{};
      var sortEl=document.getElementById('zx-m-sort');
      if(sortEl){ sortEl.value=st.sort; if(!sortEl.__zxWired){ sortEl.__zxWired=1;
        sortEl.addEventListener('change',function(){ zxMState().sort=sortEl.value; zxRenderMetrics(); }); } }
      agents.sort(function(a,b){
        var na=(a.worktree||a.name||''), nb=(b.worktree||b.name||'');
        if(st.sort==='name') return na.localeCompare(nb);
        if(st.sort==='events') return ((byAgent[nb]||0)-(byAgent[na]||0));
        var ha=a.last_activity_hours==null?1e9:a.last_activity_hours;
        var hb=b.last_activity_hours==null?1e9:b.last_activity_hours;
        return ha-hb;
      });
      tb.innerHTML='<thead><tr><th>Agent</th><th>最后活跃</th><th>24h 事件</th><th>角色</th><th>Worktree</th></tr></thead><tbody>'+
        (agents.length?agents.slice(0,15).map(function(a){
          var name=a.worktree?a.worktree.split('/').pop():(a.name||'unknown');
          var h=a.last_activity_hours;
          var cls=h==null?'#94a3b8':(h<2?'#10b981':h<72?'#f59e0b':'#94a3b8');
          var n=byAgent[name];
          return '<tr><td><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:'+cls+';margin-right:6px"></span>'+
            zxMEsc(name)+'</td><td>'+(h==null?'—':h+'h')+'</td><td>'+(n==null?'—':n)+'</td>'+
            '<td>'+(a.role?zxMEsc(a.role):'—')+'</td><td><code>'+zxMEsc(a.worktree||'—')+'</code></td></tr>';
        }).join(''):'<tr><td colspan="5" style="text-align:center;color:#94a3b8;padding:18px">无 Agent 数据</td></tr>')+'</tbody>';
    }
  }catch(err){ console.error('zxRenderMetrics failed:',err); }
}

function zxMSetRange(r){ zxMState().range=r; zxRenderMetrics(); }
function zxMToggleSeries(k){ var st=zxMState(); st.hidden[k]=!st.hidden[k]; zxRenderMetrics(); }

/* 真实重渲染钩子：供 refreshPanorama 调用（保持面板动态） */
function zxRenderPanels(live){
  /* 实时刷新入口: 先换入新快照, 再重渲三板块（真正动态, 不再读死常量） */
  if(live && typeof live==='object' && Object.keys(live).length) window.__zxLiveData=live;
  zxRenderLogs(); zxRenderMetrics(); zxRenderValue();
}
(function zxMetricsBoot(){ if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',zxRenderMetrics); else zxRenderMetrics(); })();
