/* 实时数据访问器。
   模板里 `const D` 是词法常量、不可重新赋值 —— 这也正是旧版"面板不动态"的根因:
   refreshPanorama(d) 拿到的新数据永远进不到读全局 D 的渲染函数里。
   这里用 window.__zxLiveData 承接实时快照, 各渲染函数在入口处用 `var D = zxData()`
   遮蔽全局常量, 从而真正随刷新变化。 */
function zxData(){
  if(window.__zxLiveData && Object.keys(window.__zxLiveData).length) return window.__zxLiveData;
  return (typeof D!=='undefined' && D) ? D : {};
}

/* 织星驾驶舱 · logs 板块 —— 结构化真实事件流
   数据来源: D.panel_events (由 bin/panorama/panel-collect.collect_event_stream 产出)
   真实性约束: 只渲染 payload 中存在的字段; 缺失一律显示为「—」或 MISSING, 不补 0 伪装。 */
function zxLogsState(){ if(!window.__zxLogs) window.__zxLogs={type:'',source:'',status:'',q:'',limit:30}; return window.__zxLogs; }

function zxLogsFmtRelative(iso){
  if(!iso) return '—';
  var t=Date.parse(iso); if(isNaN(t)) return iso;
  var d=Math.max(0,Math.floor((Date.now()-t)/1000));
  if(d<60) return d+'s 前';
  if(d<3600) return Math.floor(d/60)+'m 前';
  if(d<86400) return Math.floor(d/3600)+'h 前';
  return Math.floor(d/86400)+'d 前';
}
function zxLogsEsc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

function zxLogsStatusChip(status){
  if(!status) return '<span class="zx-chip dim">—</span>';
  var s=String(status).toLowerCase();
  var cls=(s==='ok'||s==='healthy'||s==='pass'||s==='accepted')?'ok'
        :(s==='failed'||s==='error'||s==='blocked'||s==='degraded')?'err':'dim';
  return '<span class="zx-chip '+cls+'">'+zxLogsEsc(status)+'</span>';
}
function zxLogsSourceChip(state){
  var cls=state==='OK'?'ok':state==='MISSING'?'err':state==='STALE'?'warn':'dim';
  return '<span class="zx-chip '+cls+'">'+zxLogsEsc(state)+'</span>';
}

/* 纯 SVG sparkline —— 真实序列, 无外部库 */
function zxSparkline(points,color){
  if(!points||!points.length) return '<div class="zx-empty"><span class="zx-state">NO DATA</span><br>暂无序列数据</div>';
  var w=320,h=74,pad=4,n=points.length,mx=0;
  for(var i=0;i<n;i++) if(points[i][1]>mx) mx=points[i][1];
  if(mx<=0) return '<div class="zx-empty"><span class="zx-state">ZERO</span><br>窗口内无事件</div>';
  var bw=Math.max(1,(w-pad*2)/n-1);
  var bars=points.map(function(p,i){
    var bh=Math.max(1,(p[1]/mx)*(h-pad*2));
    var x=pad+i*((w-pad*2)/n);
    var label=p[0].slice(5,16).replace('T',' ');
    return '<rect x="'+x.toFixed(1)+'" y="'+(h-pad-bh).toFixed(1)+'" width="'+bw.toFixed(1)+
           '" height="'+bh.toFixed(1)+'" rx="1" fill="'+(p[1]?color:'#e2e8f0')+'"><title>'+label+' → '+p[1]+'</title></rect>';
  }).join('');
  return '<svg class="zx-spark" viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none">'+bars+'</svg>';
}

function zxLogsBarList(obj,color,max){
  var keys=Object.keys(obj||{}); if(!keys.length) return '<div class="zx-empty">无数据</div>';
  var m=max||Math.max.apply(null,keys.map(function(k){return obj[k]}).concat([1]));
  return '<div class="zx-bars">'+keys.slice(0,9).map(function(k){
    var v=obj[k],pct=Math.round(v/m*100);
    return '<div class="zx-bar-row"><div class="zx-bar-head"><span title="'+zxLogsEsc(k)+'">'+zxLogsEsc(k)+'</span><span>'+v+'</span></div>'+
      '<div class="zx-bar-track"><i style="width:'+pct+'%;background:'+color+'"></i></div></div>';
  }).join('')+'</div>';
}

function zxLogsFiltered(){
  var D=zxData();
  var ev=D.panel_events||{}, st=zxLogsState();
  var all=ev.events_all||ev.events||[], q=st.q.toLowerCase();
  return all.filter(function(e){
    if(st.type && e.type!==st.type) return false;
    if(st.source && e.source!==st.source) return false;
    if(st.status && (e.status||'')!==st.status) return false;
    if(q){
      var hay=((e.summary||'')+' '+(e.agent||'')+' '+(e.run_id||'')+' '+(e.type||'')).toLowerCase();
      if(hay.indexOf(q)<0) return false;
    }
    return true;
  });
}

function zxRenderLogs(){
  try{
    var D=zxData();
    var ev=D.panel_events;
    var host=document.getElementById('zx-logs-kpis'); if(!host) return;
    if(!ev){ host.innerHTML='<div class="zx-empty"><span class="zx-state">NO DATA</span><br>未收到 panel_events 数据</div>'; return; }
    var sum=ev.summary||{}, st=zxLogsState();
    var agents=D.agents||[], active=agents.filter(function(a){return a.last_activity_hours<24}).length;

    /* ── KPI 卡（失败率与来源缺失为真实新增指标）── */
    var kpis=[
      {v:sum.events_24h||0,l:'24h 事件',bar:Math.min(100,(sum.events_24h||0)/30),c:'var(--zx-blue)'},
      {v:(sum.events_per_hour||0)+'',l:'事件/小时',bar:Math.min(100,(sum.events_per_hour||0)/3),c:'var(--zx-teal)'},
      {v:agentHealthRatio(active,agents.length),l:'活跃 Agent',bar:agents.length?active/agents.length*100:0,c:'var(--zx-violet)'},
      {v:(sum.failure_rate==null?'—':sum.failure_rate+'%'),l:'失败/阻塞率',bar:sum.failure_rate||0,c:(sum.failure_rate>10?'var(--zx-red)':'var(--zx-warn)')},
      {v:(sum.sources_live||0)+'/'+((sum.sources_live||0)+(sum.sources_missing||0)),l:'存活事件源',bar:(sum.sources_live+sum.sources_missing)?sum.sources_live/(sum.sources_live+sum.sources_missing)*100:0,c:'var(--zx-ok)'},
      {v:sum.agents_active||0,l:'出现过的 Agent',bar:Math.min(100,(sum.agents_active||0)*20),c:'var(--zx-blue)'}
    ];
    host.innerHTML=kpis.map(function(k){
      return '<div class="zx-kpi"><div class="zx-kv">'+k.v+'</div><div class="zx-kl">'+k.l+'</div>'+
        '<div class="zx-kbar"><i style="width:'+Math.max(0,Math.min(100,k.bar))+'%;background:'+k.c+'"></i></div></div>';
    }).join('');
    function agentHealthRatio(a,t){ return t?a+'/'+t:'—'; }

    /* ── 筛选器：选项来自真实分面 ── */
    function fill(sel,obj,label){
      var el=document.getElementById(sel); if(!el) return;
      var keys=Object.keys(obj||{});
      el.innerHTML='<option value="">全部'+label+'</option>'+keys.map(function(k){
        return '<option value="'+zxLogsEsc(k)+'">'+zxLogsEsc(k)+'（'+obj[k]+'）</option>';
      }).join('');
      el.value=st[sel.replace('zx-f-','')]||'';
    }
    var facets=ev.facets||{};
    fill('zx-f-type',facets.by_type,'类型');
    fill('zx-f-source',facets.by_source,'来源');
    fill('zx-f-status',facets.by_status,'状态');

    /* ── 事件流（真实筛选 + 分页）── */
    var rows=zxLogsFiltered(), total=(ev.events_all||[]).length;
    var countEl=document.getElementById('zx-logs-count');
    if(countEl) countEl.textContent='显示 '+Math.min(st.limit,rows.length)+' / '+rows.length+(rows.length!==total?'（已筛选，共 '+total+'）':'');
    var stream=document.getElementById('zx-logs-stream');
    if(stream){
      if(!rows.length){ stream.innerHTML='<div class="zx-empty"><span class="zx-state">NO MATCH</span><br>当前筛选条件下没有事件</div>'; }
      else {
        stream.innerHTML=rows.slice(0,st.limit).map(function(e){
          var dot=e.status&&/fail|error|blocked|degraded/i.test(e.status)?'var(--zx-red)'
                 :(/ok|healthy|pass/i.test(e.status||'')?'var(--zx-ok)':'var(--zx-blue)');
          var extra=[];
          if(e.duration_s!=null) extra.push('<span class="zx-tag">⏱ '+e.duration_s+'s</span>');
          if(e.check_count) extra.push('<span class="zx-tag">✓ '+e.check_count+' checks'+(e.failed_check_count?'（'+e.failed_check_count+' 失败）':'')+'</span>');
          if(e.changed_file_count) extra.push('<span class="zx-tag">📄 '+e.changed_file_count+' 文件</span>');
          return '<div class="zx-ev"><span class="zx-dot" style="background:'+dot+'"></span><div class="zx-body">'+
            '<div class="zx-sum" title="'+zxLogsEsc(e.summary)+'">'+zxLogsEsc(e.summary||e.type)+'</div>'+
            '<div class="zx-meta"><span class="zx-tag">'+zxLogsEsc(e.type)+'</span>'+
              '<span>'+zxLogsEsc(e.source)+'</span>'+
              (e.agent?'<span>· '+zxLogsEsc(e.agent)+'</span>':'')+
              (e.workflow_id?'<span>· '+zxLogsEsc(e.workflow_id)+'</span>':'')+
              zxLogsStatusChip(e.status)+extra.join('')+'</div></div>'+
            '<span class="zx-t" title="'+zxLogsEsc(e.ts)+'">'+zxLogsFmtRelative(e.ts)+'</span></div>';
        }).join('');
      }
    }
    var more=document.getElementById('zx-logs-more');
    if(more) more.innerHTML=(rows.length>st.limit)
      ? '<button type="button" onclick="zxLogsLoadMore()">加载更多（还有 '+(rows.length-st.limit)+' 条）</button>' : '';

    /* ── 24h 速率 sparkline ── */
    var spark=document.getElementById('zx-logs-spark');
    var series=ev.series||{};
    if(spark) spark.innerHTML=zxSparkline((series.hourly_24h||[]),'var(--zx-blue)');
    var note=document.getElementById('zx-spark-note');
    if(note){
      var pts=series.hourly_24h||[], peak=0, peakAt='';
      pts.forEach(function(p){ if(p[1]>peak){peak=p[1];peakAt=p[0];} });
      note.textContent=pts.length?('峰值 '+peak+' 事件/时（'+peakAt.slice(5,16).replace('T',' ')+'）· 共 '+pts.length+' 个真实小时桶'):'';
    }

    /* ── 运行态概览 ── */
    var ag=document.getElementById('zx-logs-agents');
    if(ag){
      var tick=D.agent_tick||{};
      var rowsA=agents.slice(0,8).map(function(a){
        var h=a.last_activity_hours==null?null:a.last_activity_hours;
        var cls=h==null?'var(--zx-dim)':(h<2?'var(--zx-ok)':h<72?'var(--zx-warn)':'var(--zx-dim)');
        return '<div style="display:flex;align-items:center;gap:7px;padding:3px 0">'+
          '<span style="width:6px;height:6px;border-radius:50%;background:'+cls+'"></span>'+
          '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+
            zxLogsEsc(a.worktree?a.worktree.split('/').pop():(a.name||'unknown'))+'</span>'+
          '<span style="font-size:10px;color:var(--muted)">'+(h==null?'—':h+'h')+'</span></div>';
      }).join('');
      var tickLine=(tick.ok_count!=null)
        ? '<div style="border-top:1px solid var(--line);margin-top:8px;padding-top:8px;display:flex;justify-content:space-between">'+
          '<span>最近心跳</span><span>'+tick.ok_count+' ok / '+(tick.failed_count||0)+' failed（'+tick.agent_count+' agents）</span></div>' : '';
      ag.innerHTML=(rowsA||'<div class="zx-empty">无 Agent</div>')+tickLine;
    }

    /* ── 分面分布 ── */
    var fx=document.getElementById('zx-logs-facets');
    if(fx){
      fx.innerHTML='<div style="font-size:10px;color:var(--muted);margin-bottom:4px">按类型（24h）</div>'+
        zxLogsBarList(facets.by_type,'var(--zx-blue)')+
        '<div style="font-size:10px;color:var(--muted);margin:10px 0 4px">按来源（24h）</div>'+
        zxLogsBarList(facets.by_source,'var(--zx-teal)');
    }

    /* ── 事件源健康 ── */
    var srcs=ev.sources||[], tb=document.getElementById('zx-logs-sources');
    var sc=document.getElementById('zx-logs-src-count');
    if(sc) sc.textContent=sum.sources_live+' 存活 / '+sum.sources_missing+' 缺失';
    if(tb){
      tb.innerHTML='<thead><tr><th>来源</th><th>状态</th><th>24h</th><th>累计</th><th>最后事件</th><th>文件</th></tr></thead><tbody>'+
        srcs.map(function(s){
          return '<tr><td>'+zxLogsEsc(s.label)+'<div style="font-size:9px;color:var(--muted)">'+zxLogsEsc(s.name)+'</div></td>'+
            '<td>'+zxLogsSourceChip(s.state)+(s.note?'<div style="font-size:9px;color:#c33;margin-top:2px">'+zxLogsEsc(s.note)+'</div>':'')+'</td>'+
            '<td>'+(s.window_count==null?'—':s.window_count)+'</td>'+
            '<td>'+(s.total_count==null?'—':s.total_count)+'</td>'+
            '<td>'+(s.last_ts?zxLogsFmtRelative(s.last_ts):'—')+'</td>'+
            '<td><code>'+zxLogsEsc(s.path)+'</code></td></tr>';
        }).join('')+'</tbody>';
    }
  }catch(err){ console.error('zxRenderLogs failed:',err); }
}

function zxLogsLoadMore(){ zxLogsState().limit+=30; zxRenderLogs(); }
function zxLogsSetFilter(key,val){ var st=zxLogsState(); st[key]=val; st.limit=30; zxRenderLogs(); }

(function zxLogsWire(){
  function wire(){
    var map=[['zx-f-type','type'],['zx-f-source','source'],['zx-f-status','status']];
    map.forEach(function(p){
      var el=document.getElementById(p[0]);
      if(el&&!el.__zxWired){ el.__zxWired=1; el.addEventListener('change',function(){ zxLogsSetFilter(p[1],el.value); }); }
    });
    var q=document.getElementById('zx-f-q');
    if(q&&!q.__zxWired){ q.__zxWired=1; var t=null;
      q.addEventListener('input',function(){ clearTimeout(t); t=setTimeout(function(){ zxLogsSetFilter('q',q.value.trim()); },180); }); }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',wire); else wire();
  zxRenderLogs();
})();
