'use strict';
let missionData = {missions:[],turns:[],messages:[],experiments:[],claims:[],claim_history:[],executor:{}};
const decode = value => {try{return JSON.parse(value || '{}');}catch{return {};}};
const missionStatus = status => tag(status, ['completed','peer_checked','passed','ready'].includes(status)?'green':['running','responded'].includes(status)?'blue':['failed','interrupted','unavailable','withheld','changes_requested'].includes(status)?'amber':'');
async function loadMissions() {
  const [page,id]=route();
  missionData=await api('missions'+(page==='missions'&&id?'?id='+encodeURIComponent(id):''));
}
function missions() {
  const data=missionData, m=data.missions.find(x=>x.id===data.selected);
  let html=title('MISSION CONTROL','Work worth someone’s attention.','A clear purpose. Checked evidence. A careful explanation. The team can withhold work that does not meet the bar.',btn('New mission +','mission-new','','primary'));
  if(!m) return html+'<section class="launch"><div class="eyebrow">YOUR ROLE: BIG PICTURE ORCHESTRATOR</div><h2>One mission. A working research team.</h2><p>Give the agents a research direction and a call allowance. They carry out the investigation together. You can inspect their conversation, pause, or stop the mission at any time.</p>'+btn('Set a research mission →','mission-new','','primary')+'<small>ChatGPT subscription via Codex · no API-key provider · local workspace</small></section>';
  const steps=['explore','challenge','experiment','verify','assess','conclude',...(m.context.quality_version?['write','read']:[])];
  const current=m.context.stage;
  const running=data.turns.find(t=>['running','responded'].includes(t.status));
  html+='<div class="mission-picker">'+data.missions.map(x=>'<a class="mission-chip '+(x.id===m.id?'selected':'')+'" href="#missions/'+x.id+'">'+esc(x.title)+' '+missionStatus(x.status)+'</a>').join('')+'</div>';
  html+=humanReports(data,m);
  html+='<details class="mission-process"'+((data.reports||[]).some(r=>r.status==='ready')?'':' open')+'><summary>Mission, working notes & evidence</summary><section class="mission-brief panel"><div><div class="button-row">'+missionStatus(m.status)+tag(m.provider==='demo'?'synthetic rehearsal':'ChatGPT subscription',m.provider==='demo'?'amber':'green')+'</div><h2>'+esc(m.title)+'</h2><p class="preserve">'+esc(m.objective)+'</p></div><div class="button-row">'+(['ready','paused'].includes(m.status)?btn(m.status==='paused'?'Resume mission':'Start mission','mission-start',m.id,'primary'):'')+(m.status==='running'?btn('Pause','mission-pause',m.id):'')+(['ready','paused','running'].includes(m.status)?btn('Stop','mission-stop',m.id,'danger'):'')+'</div></section>';
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
  return html+'</details>';
}
async function missionAction(action,id) {
  if(action==='mission-new') {
    const limit=(name,caption,value,min,max)=>'<label>'+caption+'<input type="number" name="'+name+'" value="'+value+'" min="'+min+'" max="'+max+'" step="1" required></label>';
    form('Give the team a mission',field('title','Mission name','Agent memory research')+field('objective','What should the team work toward?','Investigate practical improvements to agent memory and coordination. Choose a small falsifiable question, run a CPU-only Python experiment, challenge the result, and use what you learn to choose the next question.','textarea')+select('provider','Inference',[['codex','ChatGPT subscription · official Codex CLI'],['demo','Synthetic rehearsal · no inference']])+'<div class="form-row">'+limit('call_limit','Maximum calls',12,8,60)+limit('cycle_limit','Maximum cycles',1,1,6)+limit('minutes','Maximum minutes',20,2,60)+'</div><label>Model (optional)<input name="model" placeholder="Use Codex default"></label>','Start autonomous mission',async d=>{const created=await api('missions',{...d,call_limit:Number(d.call_limit),cycle_limit:Number(d.cycle_limit),minutes:Number(d.minutes)});location.hash='missions/'+created.id;await api('missions/'+created.id+'/start',{});},'Eight calls cover one research, writing, and reader-review cycle; 12 leave room for revision. Agents may withhold an unhelpful result. Subscription allowance is consumed; API keys are not supported. No purchasing, publishing, or changes to this app.');
  } else if(action==='mission-refine') {
    const created=await api('missions/'+id+'/refine',{});location.hash='missions/'+created.id;await refresh();
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

function humanReports(data,m) {
  const reports=data.reports||[];
  const ready=reports.filter(r=>r.status==='ready');
  let result=ready.map(r=>{
    const d=decode(r.content_json);
    const review=(data.report_reviews||[]).find(v=>v.version_id===r.current_version&&v.verdict==='accept');
    const checks=review?decode(review.checks_json):[];
    return '<article class="research-note"><div class="note-kicker">'+esc(m.provider==='demo'?'SYNTHETIC REHEARSAL':'EMERGENCE LAB · RESEARCH NOTE')+' '+missionStatus('ready')+'</div>'
      +'<h2>'+esc(d.title)+'</h2><p class="note-takeaway">'+esc(d.takeaway)+'</p><p class="note-audience">For '+esc(d.audience)+'</p>'
      +'<section><h3>Why it matters</h3><p>'+esc(d.why_it_matters)+'</p></section>'
      +'<div class="note-comparison"><section><h3>What was tested</h3><p>'+esc(d.what_was_tested)+'</p></section><section><h3>What we found</h3><p>'+esc(d.result)+'</p></section></div>'
      +'<section class="note-action"><h3>What you can do</h3><p>'+esc(d.what_to_do)+'</p></section>'
      +'<section><h3>Where this stops</h3><p>'+esc(d.limitations)+'</p></section><section><h3>The next useful step</h3><p>'+esc(d.next_step)+'</p></section>'
      +'<div class="note-footer"><a class="btn primary" href="/api/reports/'+esc(r.id)+'/download">Download research note ↓</a><span>'+esc(r.reader_feedback?'Your feedback: '+r.reader_feedback.replaceAll('_',' '):'Reviewed by agents · human usefulness untested')+'</span></div><div class="button-row section-gap">'+btn('Useful to me','report-feedback-useful',r.id,'small')+btn('Not useful','report-feedback-not_useful',r.id,'small')+'</div>'
      +'<details class="note-review"><summary>Review & traceable evidence</summary>'+checks.map(c=>'<p><b>'+label(c.criterion)+'</b> · '+esc(c.reason)+'</p>').join('')+'<p class="mono">Evidence: '+esc(d.evidence_ids.join(', '))+'</p><p class="mono">Edition: '+esc(r.current_version)+'</p></details></article>';
  }).join('');
  if(!ready.length) {
    const pending=reports[0];
    result='<section class="quality-status panel panel-content"><div class="eyebrow">THE OUTPUT STANDARD</div><h2>'+esc(pending?.status==='withheld'?'Withheld after review':m.context.quality_version?'Nothing ready to share yet':'This work has not had a reader review')+'</h2><p>'+esc(pending?.reason || (m.context.quality_version?'The team must show who this helps, check the evidence, write a clear note, and pass a fresh reader review. A completed mission can produce no finished report.':'Scientific review and a useful human explanation are separate. Prepare one checked finding as a concise research note.'))+'</p>'
      +(!m.context.quality_version&&data.claims.some(c=>c.status==='peer_checked')?btn('Prepare a research note','mission-refine',m.id,'primary')+'<p class="form-hint">Uses up to four subscription calls for writing, review, and one possible revision. Rehearsals use no inference.</p>':'')+'</section>';
  }
  if(reports.length) result+='<details class="report-history panel panel-content"><summary>Drafts & quality decisions</summary>'+reports.map(r=>'<div class="run-record">'+missionStatus(r.status)+'<p>'+esc(r.reason)+'</p>'+(data.report_versions||[]).filter(v=>v.report_id===r.id).map(v=>'<details><summary>Edition '+esc(v.id)+'</summary><pre class="code">'+esc(JSON.stringify(decode(v.content_json),null,2))+'</pre>'+(data.report_reviews||[]).filter(x=>x.version_id===v.id).map(x=>'<p>'+esc(x.notes)+'</p><pre class="code">'+esc(JSON.stringify(decode(x.checks_json),null,2))+'</pre>').join('')+'</details>').join('')+'</div>').join('')+'</details>';
  return result;
}

function reportFeedback(id,value) {
  form('Help the team aim better',field('reason','What made this useful or unhelpful?','','textarea'),'Save feedback',d=>api('reports/'+id+'/feedback',{value,reason:d.reason}),'Feedback guides future missions. Agents continue without waiting for it.');
}
