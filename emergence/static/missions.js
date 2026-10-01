'use strict';
let missionData = {missions:[],turns:[],messages:[],experiments:[],claims:[],claim_history:[],executor:{}};
let missionLoadGeneration = 0;
const decode = value => {try{return JSON.parse(value || '{}');}catch{return {};}};
const missionStatus = status => tag(status, ['completed','peer_checked','passed','ready'].includes(status)?'green':['running','responded'].includes(status)?'blue':['failed','interrupted','unavailable','withheld','changes_requested'].includes(status)?'amber':'');
async function loadMissions() {
  const [page,id]=route();
  const generation=++missionLoadGeneration, hash=location.hash;
  const result=await api('missions'+(['missions','reports'].includes(page)&&id?'?id='+encodeURIComponent(id):''));
  if(generation!==missionLoadGeneration||hash!==location.hash) return false;
  missionData=result;
  return true;
}
function missions(id) {
  if(!id) return labOverview();
  const data=missionData, m=data.missions.find(x=>x.id===data.selected);
  let html='<a class="back" href="#overview">← Overview</a>'+title('WORKING RECORDS','Mission details',esc(m?.title||'Choose a mission'),btn('New mission','mission-new','','primary'));
  if(!m) return html+empty('Mission not found','Choose a mission from the overview or mission history.');
  const steps=['explore','challenge','experiment','verify','assess','conclude',...(m.context.quality_version?['write','read']:[])];
  const current=m.context.stage;
  const running=data.turns.find(t=>['running','responded'].includes(t.status));
  if((data.reports||[]).some(r=>r.status==='ready')) html+='<div class="detail-result-link"><span>A reviewed research note is available.</span><a class="btn small" href="#reports/'+encodeURIComponent(m.id)+'">Read report →</a></div>';
  else html+=humanReports(data,m);
  html+='<details class="mission-process" open><summary>Mission, working notes & evidence</summary><section class="mission-brief panel"><div><div class="button-row">'+missionStatus(m.status)+tag(m.provider==='demo'?'synthetic rehearsal':'ChatGPT subscription',m.provider==='demo'?'amber':'green')+'</div><h2>'+esc(m.title)+'</h2><p class="preserve">'+esc(m.objective)+'</p></div><div class="button-row">'+(['ready','paused'].includes(m.status)?btn(m.status==='paused'?'Resume mission':'Start mission','mission-start',m.id,'primary'):'')+(m.status==='running'?btn('Pause','mission-pause',m.id):'')+(['ready','paused','running'].includes(m.status)?btn('Stop','mission-stop',m.id,'danger'):'')+'</div></section>';
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
    form('New mission',field('title','Mission name','Agent memory research')+field('objective','What should the team work toward?','Improve how AI agents remember and use evidence. Choose a useful question, run a small experiment, and produce a clear report.','textarea')+select('provider','Inference',[['codex','ChatGPT subscription · official Codex CLI'],['demo','Synthetic rehearsal · no inference']])+limit('call_limit','Call allowance',12,8,60)+'<details class="form-options"><summary>More settings</summary><div class="form-row">'+limit('cycle_limit','Maximum cycles',1,1,6)+limit('minutes','Maximum minutes',20,2,60)+'</div><label>Model (optional)<input name="model" placeholder="Use Codex default"></label></details>','Start mission',async d=>{const created=await api('missions',{...d,call_limit:Number(d.call_limit),cycle_limit:Number(d.cycle_limit),minutes:Number(d.minutes)});location.hash='overview';await api('missions/'+created.id+'/start',{});},'Uses your ChatGPT subscription. 12 calls allow one research and review cycle with room for revision. Agents may finish without a publishable report.');
  } else if(action==='mission-refine') {
    const created=await api('missions/'+id+'/refine',{});location.hash='overview';await refresh();
  } else {
    await api('missions/'+id+'/'+action.replace('mission-',''),{});
    await refresh();
  }
}
setInterval(async()=>{
  if(!['overview','missions','reports','history'].includes(route()[0])||document.hidden||$('modal').open||!missionData.missions.some(m=>m.status==='running')) return;
  try {
    const open=[...document.querySelectorAll('#content details')].map((e,i)=>e.open?i:-1).filter(i=>i>=0);
    if(!await loadMissions()) return;
    render();
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

function reportPage() {
  const m=missionData.missions.find(x=>x.id===missionData.selected);
  if(!m) return '<a class="back" href="#overview">← Overview</a>'+empty('Report not found','Choose a report from the overview.');
  return '<a class="back" href="#overview">← Overview</a>'
    +title('RESEARCH NOTE','Report','Reviewed by the agents. Evidence and limitations are included.',
      '<a class="btn" href="#missions/'+encodeURIComponent(m.id)+'">Working records</a>')
    +humanReports(missionData,m);
}

const missionLink = (m,page='missions') => '#'+page+'/'+encodeURIComponent(m.id);
const phaseIndex = stage => ({explore:0,challenge:0,experiment:1,verify:2,assess:2,conclude:2,write:3,read:3}[stage] ?? 0);
function teamFlow(m) {
  const active=m?.status==='running', index=phaseIndex(m?.context.stage);
  return '<ol class="team-flow" aria-label="How the agents work">'
    +[['Research','Scout + critic'],['Experiment','Researcher'],['Verify','Critic + coordinator'],['Write & review','Editor + reader']].map(([name,roles],i)=>
      '<li'+(active&&index===i?' class="active" aria-current="step"':'')+'><span class="flow-number" aria-hidden="true">'+(i+1)+'</span><div><b>'+name+'</b><small>'+roles+'</small></div></li>').join('')+'</ol>';
}

function missionRows(items) {
  return items.map(m=>'<a class="history-row" href="'+missionLink(m)+'"><div><b>'+esc(m.title)+'</b><small>'
    +esc(m.provider==='demo'?'Rehearsal · no inference':m.ready_reports_count?m.ready_reports_count+' reviewed report'+(m.ready_reports_count===1?'':'s'):'No reviewed report')
    +' · '+m.calls_used+'/'+m.call_limit+' calls</small></div>'+missionStatus(m.status)+'<span aria-hidden="true">→</span></a>').join('');
}

function missionHistory() {
  const live=missionData.missions.filter(m=>m.provider!=='demo');
  const demo=missionData.missions.filter(m=>m.provider==='demo');
  return '<a class="back" href="#overview">← Overview</a>'+title('RECORDS','Mission history','Research runs and their working records.')
    +'<section class="panel history-list">'+(missionRows(live)||empty('No research missions yet','Start one from the overview.'))+'</section>'
    +(demo.length?'<details class="history-disclosure"><summary>Rehearsals ('+demo.length+')</summary><div class="panel history-list">'+missionRows(demo)+'</div></details>':'');
}

function labOverview() {
  const data=missionData, all=data.missions, live=all.filter(m=>m.provider!=='demo');
  const running=all.find(m=>m.status==='running');
  const m=running||all.find(m=>m.status==='paused')||all.find(m=>m.status==='ready')||live[0]||all[0];
  const report=data.overview?.recent_reports?.[0]||data.overview?.demo_reports?.[0];
  const demoReport=report?.provider==='demo';
  const count=data.overview?.counts?.live?.ready_reports||0;
  const stateText=running?'Working':m?.status==='paused'?'Paused':m?.status==='failed'?'Stopped':'Idle';
  const needsAttention=m?.status==='paused'||m?.status==='failed';
  const controls=m?.status==='running'?btn('Pause','mission-pause',m.id,'small')
    :m?.status==='paused'?btn('Resume mission','mission-start',m.id,'small')
    :m?.status==='ready'?btn('Start mission','mission-start',m.id,'small'):'';
  const activity=m?.status==='running'
    ?(m.context.consult?'The agents are discussing a question.':({explore:'The scout is choosing a question.',challenge:'The critic is checking the research plan.',experiment:'The researcher is running an experiment.',verify:'The critic is testing the result.',assess:'The critic is assessing the evidence.',conclude:'The coordinator is drawing a conclusion.',write:'The editor is preparing a report.',read:'The reader is reviewing the draft.'}[m.context.stage]||'The team is working.'))
    :m?.status==='paused'?'This mission is paused. Check its details before resuming.'
    :m?.status==='failed'?'This mission stopped after an error. Open its records to inspect the cause.'
    :m?.status==='ready'?'A mission is ready to start.'
    :m&&['completed','exhausted'].includes(m.status)?(m.ready_reports_count?'The last mission produced a reviewed report. No mission is running.':'The last mission ended without a reviewed report. No mission is running.')
    :'No mission is running. Start a new one when you have a direction to explore.';
  const focus=m?.context.candidate?.question||m?.objective;
  const phase=['running','paused','ready'].includes(m?.status)?'Current research question':'Last research question';
  const direction='<p class="overview-label">Lab direction</p><h2>Develop better AI through agent collaboration.</h2>'
    +(m?'<details class="focus-detail"><summary>'+phase+'</summary><p>'+esc(focus||m.title)+'</p></details>'
      +'<div class="focus-footer"><span>'+esc(m.provider==='demo'?'Synthetic rehearsal':m.title)+'</span><a href="'+missionLink(m)+'">Mission details →</a></div>'
      :'<p class="overview-copy">Start with a question. The team will investigate it and prepare a report if the evidence holds up.</p>');
  const status='<section class="overview-card team-card'+(needsAttention?' attention':'')+'"><div class="overview-card-top"><h2>Team status</h2><span class="status-label"><span class="status-dot '+stateText.toLowerCase()+'" aria-hidden="true"></span>'+stateText+'</span></div>'
    +'<p class="team-activity">'+esc(activity)+'</p>'
    +(m&&['running','paused','ready'].includes(m.status)?'<div class="team-budget"><span>'+m.calls_used+' of '+m.call_limit+' calls used</span><progress aria-label="Mission calls used" value="'+m.calls_used+'" max="'+m.call_limit+'"></progress></div>':'<p class="team-footnote">Agents work within the mission’s call allowance.</p>')
    +(controls?'<div class="button-row">'+controls+'</div>':'')+'</section>';
  const output=report
    ?'<article class="overview-card result-preview"><div class="overview-card-top"><h2>'+ (demoReport?'Rehearsal result':'Latest result')+'</h2><span class="result-state">'+(demoReport?'Synthetic · no inference':'Agent reviewed')+'</span></div><h3>'+esc(report.title)+'</h3><p>'+esc(report.takeaway)+'</p><div class="result-preview-footer"><a class="btn" href="#reports/'+encodeURIComponent(report.mission_id)+'">Read report →</a><span>'+(demoReport?'Fixed responses · not a research finding':count+' reviewed report'+(count===1?'':'s'))+'</span></div></article>'
    :'<section class="overview-card result-preview empty-result"><div class="overview-card-top"><h2>Latest result</h2></div><h3>No reviewed report yet.</h3><p>Results appear here after evidence checks and a separate reader review. Working notes stay in mission records.</p></section>';
  const earlier=all.filter(x=>x.id!==m?.id);
  return '<div class="overview-heading"><div><h1>Overview</h1><p>AI research by your agents. You set the direction.</p></div>'+btn('New mission','mission-new','','primary')+'</div>'
    +'<div class="lab-overview"><div class="overview-top"><section class="overview-card direction-card">'+direction+'</section>'+status+'</div>'
    +teamFlow(running)+output
    +(earlier.length?'<details class="history-disclosure"><summary>Earlier missions <span>'+earlier.length+'</span></summary><div class="panel history-list">'+missionRows(earlier.slice(0,4))+'</div><a class="history-more" href="#history">View all mission records →</a></details>':'')+'</div>';
}
