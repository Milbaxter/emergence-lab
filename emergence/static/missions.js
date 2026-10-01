'use strict';
let missionData = {missions:[],turns:[],messages:[],experiments:[],claims:[],claim_history:[],executor:{}};
const decode = value => {try{return JSON.parse(value || '{}');}catch{return {};}};
const missionStatus = status => tag(status, ['completed','peer_checked','passed'].includes(status)?'green':['running','responded'].includes(status)?'blue':['failed','interrupted','unavailable'].includes(status)?'amber':'');
async function loadMissions() {
  const [page,id]=route();
  missionData=await api('missions'+(page==='missions'&&id?'?id='+encodeURIComponent(id):''));
}
function missions() {
  const data=missionData, m=data.missions.find(x=>x.id===data.selected);
  let html=title('MISSION CONTROL','Set the direction. Let the team work.','Agents choose questions, challenge methods, run experiments, and decide what to investigate next.',btn('New mission +','mission-new','','primary'));
  if(!m) return html+'<section class="launch"><div class="eyebrow">YOUR ROLE: BIG PICTURE ORCHESTRATOR</div><h2>One mission. A working research team.</h2><p>Give the agents a research direction and a call allowance. They carry out the investigation together. You can inspect their conversation, pause, or stop the mission at any time.</p>'+btn('Set a research mission →','mission-new','','primary')+'<small>ChatGPT subscription via Codex · no API-key provider · local workspace</small></section>';
  const steps=['explore','challenge','experiment','verify','assess','conclude'];
  const current=m.context.stage;
  const running=data.turns.find(t=>['running','responded'].includes(t.status));
  html+='<div class="mission-picker">'+data.missions.map(x=>'<a class="mission-chip '+(x.id===m.id?'selected':'')+'" href="#missions/'+x.id+'">'+esc(x.title)+' '+missionStatus(x.status)+'</a>').join('')+'</div>';
  html+='<section class="mission-brief panel"><div><div class="button-row">'+missionStatus(m.status)+tag(m.provider==='demo'?'synthetic rehearsal':'ChatGPT subscription',m.provider==='demo'?'amber':'green')+'</div><h2>'+esc(m.title)+'</h2><p class="preserve">'+esc(m.objective)+'</p></div><div class="button-row">'+(['ready','paused'].includes(m.status)?btn(m.status==='paused'?'Resume mission':'Start mission','mission-start',m.id,'primary'):'')+(m.status==='running'?btn('Pause','mission-pause',m.id):'')+(['ready','paused','running'].includes(m.status)?btn('Stop','mission-stop',m.id,'danger'):'')+'</div></section>';
  html+='<div class="stats section-gap"><div class="stat"><span class="stat-label">Call allowance</span><b class="stat-value">'+m.calls_used+' <small>/ '+m.call_limit+'</small></b><span class="stat-note">Attempts count, including failures</span></div><div class="stat"><span class="stat-label">Research cycle</span><b class="stat-value">'+m.context.cycle+' <small>/ '+m.cycle_limit+'</small></b><span class="stat-note">'+m.minutes+' minute mission deadline</span></div><div class="stat"><span class="stat-label">Recorded tokens</span><b class="stat-value">'+Number(m.input_tokens+m.output_tokens).toLocaleString()+'</b><span class="stat-note">'+m.input_tokens.toLocaleString()+' in · '+m.output_tokens.toLocaleString()+' out</span></div><div class="stat"><span class="stat-label">Evidence recorded</span><b class="stat-value">'+data.claims.length+'</b><span class="stat-note">'+data.experiments.length+' execution receipts</span></div></div>';
  html+='<ol class="mission-stages" aria-label="Research cycle">'+steps.map((s,i)=>'<li class="'+(s===current?'current':'')+'"><span>'+String(i+1).padStart(2,'0')+'</span>'+label(s)+'</li>').join('')+'</ol>';
  if(m.provider==='demo') html+='<div class="notice amber">Synthetic rehearsal: fixed responses exercise the workflow. These findings are excluded from live agent memory.</div>';
  if(!data.executor.available) html+='<div class="notice amber">'+esc(data.executor.details)+'</div>';
  if(m.stop_reason) html+='<div class="notice">'+esc(m.stop_reason)+'</div>';
  if(running) html+='<div class="notice live-note"><span class="live-dot"></span>'+label(running.agent)+' is working on '+label(running.stage)+'. This view updates automatically. Pausing prevents the next step; the current subscription request may finish.</div>';
  html+='<div class="mission-columns"><div><section class="panel"><div class="panel-head"><h2>Agent conversation</h2><span class="muted">'+data.turns.length+' turns</span></div><div class="mission-dialogue">'+(data.messages.filter(x=>x.kind!=='execution').map(x=>'<article class="mission-message '+esc(x.sender)+'"><div class="message-meta"><b>'+label(x.sender)+'</b><span>→ '+label(x.recipient)+'</span>'+tag(x.kind)+'<time>'+esc(new Date(x.created_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}))+'</time></div><p class="preserve">'+esc(x.body)+'</p></article>').join('')||empty('The team is ready','Start the mission to begin.'))+'</div></section></div><div class="stack">';
  html+='<section class="panel panel-content"><div class="eyebrow">CURRENT QUESTION</div><h2>'+esc(m.context.candidate.question||'The scout will choose the first question.')+'</h2><p class="mission-copy">'+esc(m.context.candidate.hypothesis||'')+'</p>'+(m.context.next_question?'<div class="eyebrow section-gap">NEXT DIRECTION</div><p>'+esc(m.context.next_question)+'</p>':'')+'</section>';
  html+='<section class="panel"><div class="panel-head"><h2>Experiment evidence</h2></div><div class="panel-content">'+(data.experiments.map(x=>{const r=decode(x.receipt_json);return '<details class="run-record"><summary>'+missionStatus(r.status)+' '+label(x.kind)+' · cycle '+x.cycle+'</summary><p class="form-hint">'+esc(r.backend||'Executor')+' · '+(r.elapsed_ms||0)+' ms</p><pre class="code">'+esc(JSON.stringify(r.data || {stderr:r.stderr,status:r.status},null,2))+'</pre><details><summary>Code & full receipt</summary><pre class="code">'+esc(x.code)+'</pre><pre class="code">'+esc(JSON.stringify(r,null,2))+'</pre></details></details>';}).join('')||'<p class="muted">Executed code and measured results will appear here.</p>')+'</div></section>';
  html+='<section class="panel"><div class="panel-head"><h2>Shared findings</h2></div><div class="panel-content">'+(data.claims.map(x=>'<article class="claim-record">'+missionStatus(x.status)+'<p>'+esc(x.statement)+'</p><p class="form-hint">'+esc(x.limitations)+'</p><details><summary>Provenance & amendments</summary><pre class="code">'+esc(JSON.stringify({id:x.id,evidence:decode(x.evidence_json),history:data.claim_history.filter(h=>h.claim_id===x.id)},null,2))+'</pre></details></article>').join('')||'<p class="muted">The coordinator records what the evidence supports, including inconclusive results.</p>')+'<p class="form-hint section-gap">Peer checked means this team accepted two successful executions and a positive verification result. It is not independent scientific validation.</p></div></section>';
  html+='</div></div><details class="panel panel-content section-gap"><summary>Turn receipts & subscription usage</summary>'+data.turns.map(t=>'<details class="run-record"><summary>#'+t.ordinal+' '+label(t.agent)+' · '+label(t.stage)+' '+missionStatus(t.status)+'</summary><pre class="code">'+esc(JSON.stringify({error:t.error,usage:decode(t.usage_json),response:decode(t.response_json)},null,2))+'</pre></details>').join('')+'</details>';
  return html;
}
async function missionAction(action,id) {
  if(action==='mission-new') {
    const limit=(name,caption,value,min,max)=>'<label>'+caption+'<input type="number" name="'+name+'" value="'+value+'" min="'+min+'" max="'+max+'" step="1" required></label>';
    form('Give the team a mission',field('title','Mission name','Agent memory research')+field('objective','What should the team work toward?','Investigate practical improvements to agent memory and coordination. Choose a small falsifiable question, run a CPU-only Python experiment, challenge the result, and use what you learn to choose the next question.','textarea')+select('provider','Inference',[['codex','ChatGPT subscription · official Codex CLI'],['demo','Synthetic rehearsal · no inference']])+'<div class="form-row">'+limit('call_limit','Maximum calls',12,6,60)+limit('cycle_limit','Maximum cycles',2,1,6)+limit('minutes','Maximum minutes',20,2,60)+'</div><label>Model (optional)<input name="model" placeholder="Use Codex default"></label>','Start autonomous mission',async d=>{const created=await api('missions',{...d,call_limit:Number(d.call_limit),cycle_limit:Number(d.cycle_limit),minutes:Number(d.minutes)});location.hash='missions/'+created.id;await api('missions/'+created.id+'/start',{});},'Agents make routine research decisions within these limits. Subscription allowance is consumed; API keys are not supported. No purchasing, publishing, or changes to this app.');
  } else {
    await api('missions/'+id+'/'+action.replace('mission-',''),{});
    await refresh();
  }
}
setInterval(async()=>{
  if(route()[0]!=='missions'||document.hidden||$('modal').open||!missionData.missions.some(m=>m.status==='running')) return;
  try {
    const open=[...document.querySelectorAll('#content details')].map((e,i)=>e.open?i:-1).filter(i=>i>=0);
    await loadMissions();render();
    const details=document.querySelectorAll('#content details');open.forEach(i=>{if(details[i])details[i].open=true;});
  } catch { /* Keep the existing evidence visible if the server is restarting. */ }
},2500);
