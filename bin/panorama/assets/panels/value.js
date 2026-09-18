/* 织星驾驶舱 · value 板块 —— 真实价值证据, 严格 NOT_PROVEN
   数据来源: D.panel_value (bin/panorama/panel-collect.collect_value_evidence)
   红线: 不得出现任何硬编码计数; 样本不足时比率指标显示 UNKNOWN(不可判定), 不得显示达标绿色。 */
function zxVEsc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

function zxVFmtDuration(sec){
  if(sec==null) return '—';
  if(sec<60) return sec+'s';
  if(sec<3600) return Math.round(sec/60)+'m';
  return (Math.round(sec/360)/10)+'h';
}

function zxRenderValue(){
  try{
    var D=zxData();
    var v=D.panel_value;
    var host=document.getElementById('zx-v-stages'); if(!host) return;
    if(!v){
      host.innerHTML='<div class="zx-nodata"><span class="zx-state">NO DATA</span><br>未收到 panel_value 数据</div>';
      return;
    }
    var s=v.samples||{};

    /* ── 状态横幅：始终来自 payload.state ── */
    var badge=document.getElementById('zx-v-badge');
    var title=document.getElementById('zx-v-state-title');
    var reasons=document.getElementById('zx-v-reasons');
    if(badge){
      badge.textContent=v.state||'UNKNOWN';
      var notProven=(v.state||'')!=='PROVEN';
      badge.style.background=notProven?'#f59e0b':'#10b981';
    }
    if(title) title.textContent=(v.state==='PROVEN')?'价值已证明':'价值尚未证明';
    if(reasons){
      var rs=(v.state_reason||[]);
      reasons.innerHTML=rs.length?rs.map(function(r){return '<li>'+zxVEsc(r)+'</li>';}).join('')
        :'<li>无可展示的原因（payload 未提供 state_reason）</li>';
    }

    /* ── 五阶段回路：真实计数, 无数据用 NO_DATA ── */
    var stages=v.stages||[];
    var chip=document.getElementById('zx-v-loop-chip');
    var okN=stages.filter(function(x){return x.count>0}).length;
    if(chip) chip.textContent=okN+' / '+stages.length+' 阶段有数据';
    var numerals=['①','②','③','④','⑤'];
    var palette=['#3a64b3','#2e7e79','#ac721a','#2e7e79','#8b5cf6'];
    host.innerHTML=stages.length?stages.map(function(stg,i){
      var has=stg.count>0;
      return '<div class="zx-v-stage'+(has?'':' nodata')+'">'+
        '<span class="zx-v-edge" style="background:'+(has?palette[i%5]:'#dde5ee')+'"></span>'+
        '<div class="zx-v-n">'+(numerals[i]||'')+'</div>'+
        '<div class="zx-v-name">'+zxVEsc(stg.name)+'</div>'+
        '<div class="zx-v-count" style="color:'+(has?'inherit':'#a8b8c8')+'">'+(has?stg.count:'—')+'</div>'+
        '<div class="zx-v-src">'+(has?'':'NO_DATA · ')+zxVEsc(stg.source)+'</div></div>';
    }).join(''):'<div class="zx-nodata">无阶段数据</div>';

    /* ── 门槛进度：真实 current / target, 不可判定显示 UNKNOWN ── */
    function renderThr(list,elId){
      var el=document.getElementById(elId); if(!el) return;
      if(!list||!list.length){ el.innerHTML='<div class="zx-nodata">无门槛定义</div>'; return; }
      el.innerHTML=list.map(function(t){
        var hasVal=(t.current!=null);
        var pct=hasVal?Math.max(0,Math.min(100,(t.current/t.target)*100)):0;
        var met=t.met;
        var color=met===true?'#10b981':met===false?'#f59e0b':'#c3cfdb';
        var chip=met===true?'<span class="zx-chip ok">达标</span>'
               :met===false?'<span class="zx-chip warn">未达标</span>'
               :'<span class="zx-chip dim">不可判定</span>';
        return '<div class="zx-v-thr-row"><div class="zx-v-thr-head">'+
          '<span>'+zxVEsc(t.label)+' '+chip+'</span>'+
          '<span style="font-family:var(--mono);font-size:10.5px;color:#7a8fa3">'+
            (hasVal?t.current:'—')+' / '+t.target+' '+zxVEsc(t.unit)+'</span></div>'+
          '<div class="zx-v-thr-track"><i style="width:'+pct+'%;background:'+color+'"></i></div>'+
          (t.gate?'<div class="zx-v-thr-note">⚠ '+zxVEsc(t.gate)+'</div>':'')+
        '</div>';
      }).join('');
    }
    renderThr(v.thresholds,'zx-v-thr');
    renderThr(v.vision_thresholds,'zx-v-vision');

    /* ── 价值证据时间线（真实记录） ── */
    var evc=document.getElementById('zx-v-ev-chip');
    var recs=v.evidence||[];
    if(evc) evc.textContent=(s.records||0)+' 条记录 · '+(s.qualifying||0)+' 条计入价值门';
    var evHost=document.getElementById('zx-v-evidence');
    if(evHost){
      evHost.innerHTML=recs.length?recs.map(function(e){
        var verdict=e.verdict||'—';
        var cls=(verdict==='accept'||verdict==='accepted')?'ok':(verdict==='reject'||verdict==='rejected')?'err':'warn';
        return '<div class="zx-v-ev"><div class="zx-v-evtop">'+
          '<span><b>'+zxVEsc(e.scene_id||'—')+'</b></span>'+
          '<span class="zx-chip '+cls+'">'+zxVEsc(verdict)+'</span></div>'+
          '<div style="color:#7a8fa3;font-size:10px;margin-top:3px">'+
            zxVEsc(e.ts||'—')+' · qualifying='+(e.qualifying?'true':'false')+
            ' · 净节省 '+zxVFmtDuration(e.saved_seconds)+
            (e.run_id?' · <code>'+zxVEsc(e.run_id)+'</code>':'')+
            ' · 来源 '+zxVEsc(e.source)+'</div></div>';
      }).join(''):'<div class="zx-nodata"><span class="zx-state">NO EVIDENCE</span><br>尚无任何价值证据记录</div>';
    }
  }catch(err){ console.error('zxRenderValue failed:',err); }
}

(function zxValueBoot(){ if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',zxRenderValue); else zxRenderValue(); })();
