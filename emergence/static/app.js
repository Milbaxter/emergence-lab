'use strict';
let state, search = '';
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const usd = n => '$' + (Number(n || 0) / 1000000).toFixed(2);
const precise = n => n === null ? 'Unsettled' : '$' + (n / 1000000).toFixed(4);
const label = s => esc(String(s).replaceAll('_', ' '));
const tag = (s, cls = '') => '<span class="tag '+cls+'">'+label(s)+'</span>';
const btn = (text, action, id = '', cls = '') => '<button class="btn '+cls+'" data-action="'+action+'" data-id="'+esc(id)+'">'+esc(text)+'</button>';
const title = (eyebrow, name, subtitle, action = '') => '<div class="page-heading"><div><div class="eyebrow">'+eyebrow+'</div><h1>'+name+'</h1><p class="subtitle">'+subtitle+'</p></div>'+action+'</div>';
const empty = (heading, body) => '<div class="empty"><h3>'+heading+'</h3><p>'+body+'</p></div>';
const agentName = id => state.agents.find(a => a.id === id)?.name || id;
const route = () => (location.hash.slice(1) || 'overview').split('/');
async function api(path, payload) {
  const r = await fetch('/api/'+path, payload === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json','X-Lab-Request':'1'},body:JSON.stringify(payload)});
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || 'Request failed.');
  return data;
}
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('toast').hidden = true, 5000); }
async function refresh() { state = await api('state'); render(); }
function budgetPanel() {
  const b = state.budget;
  return '<section class="panel"><div class="panel-head"><h2>Cash budget</h2>'+tag(b.paused?'paused':'within limit',b.paused?'amber':'green')+'</div><div class="panel-content"><div class="budget-number">'+usd(b.available_micro)+' <small>available</small></div><progress aria-label="Committed monthly budget" max="'+Math.max(1,b.limit_micro)+'" value="'+(b.spent_micro+b.reserved_micro)+'"></progress><div class="budget-detail"><span>Recorded spend</span><b>'+usd(b.spent_micro)+'</b></div><div class="budget-detail"><span>Reserved for jobs</span><b>'+usd(b.reserved_micro)+'</b></div><div class="budget-detail"><span>Monthly ceiling · '+esc(b.month)+'</span><b>'+usd(b.limit_micro)+'</b></div><div class="button-row">'+btn(b.paused?'Resume claims':'Pause claims','pause','','small')+btn('Set limit','budget','','small')+'</div><p class="form-hint">OAuth workers use your subscription allowance. This cash ledger does not measure subscription quota.</p></div></section>';
}
function proposalCards(items) {
  return items.map(p => '<a class="panel proposal-card" href="#proposals/'+p.id+'"><div class="card-top">'+tag(p.area,'blue')+tag(p.status,p.status==='approved'?'green':'')+'</div><h2>'+esc(p.title)+'</h2><p>'+esc(p.question)+'</p><div class="proposal-meta"><span>'+usd(p.budget_micro)+' project ceiling</span><span>'+state.ballots.filter(b=>b.proposal_id===p.id).length+' advisory ballots ↗</span></div></a>').join('');
}
function overview() {
  const accepted = state.artifacts.filter(a=>a.review_status==='accepted'&&!a.is_demo).length;
  return title('A COLLECTIVE RESEARCH WORKSPACE','Small agents. Open questions.','Turn shared inference into evidence you can inspect.')
    +'<div class="stats"><div class="stat"><span class="stat-label">Research sources</span><b class="stat-value">'+state.atlas.length+'</b><span class="stat-note">Across the open AI stack</span></div><div class="stat"><span class="stat-label">Active proposals</span><b class="stat-value">'+state.proposals.filter(p=>['discussion','approved'].includes(p.status)).length+'</b><span class="stat-note">Questions worth testing</span></div><div class="stat"><span class="stat-label">Agent roles</span><b class="stat-value">4</b><span class="stat-note">One owner · advisory governance</span></div><div class="stat"><span class="stat-label">Accepted findings</span><b class="stat-value">'+accepted+'</b><span class="stat-note">Excludes synthetic demo artifacts</span></div></div>'
    +'<div class="overview-grid"><section class="launch"><div class="eyebrow">START WITH A REHEARSAL</div><h2>Give the organism<br>a question to work on.</h2><p>Follow a proposal through agent ballots, a queued job, an artifact, and a separate review. Every step leaves a record.</p>'+btn('Run a free demo cycle ↗','demo','','primary')+'<small>Fixed responses · $0 inference · clearly labeled demo</small></section>'+budgetPanel()+'</div>'
    +'<section class="section-gap"><div class="section-heading"><h2>Research agenda</h2><a href="#proposals">View all →</a></div><div class="cards">'+proposalCards(state.proposals.filter(p=>['discussion','approved'].includes(p.status)).slice(0,2))+'</div></section>'
    +'<section class="section-gap"><div class="section-heading"><h2>Your research team</h2><a href="#agents">Connect workers →</a></div><div class="agent-strip">'+state.agents.map(a=>'<div class="agent-mini"><div class="avatar '+a.role+'">'+a.name[0]+'</div><div><b>'+esc(a.name)+'</b><small>'+esc(a.description)+'</small></div></div>').join('')+'</div></section>'
    +'<section class="panel section-gap"><div class="panel-head"><h2>Lab notebook</h2><span class="muted">Recent activity</span></div><div class="panel-content">'+events(state.events.slice(0,5))+'</div></section>';
}
function events(items) { return items.map(e=>'<div class="event"><span class="event-mark"></span><div><p>'+esc(e.message)+'</p><small>'+esc(agentName(e.actor))+' · '+esc(new Date(e.created_at).toLocaleString())+'</small></div></div>').join(''); }
function atlas() {
  const items=state.atlas.filter(a=>(a.title+' '+a.area+' '+a.summary).toLowerCase().includes(search.toLowerCase()));
  return title('SHARED KNOWLEDGE','Research atlas','A source map for the full AI stack. Claims carry their evidence level.',btn('Add source +','source','','primary'))
    +'<div class="notice">These are starting points, not a live ranking of state of the art. “Source reported” means the source makes the claim; this lab has not reproduced it.</div><div class="toolbar"><input id="search" aria-label="Search research sources" placeholder="Search models, memory, evaluation…" value="'+esc(search)+'"><span class="count">'+items.length+' sources</span></div><div class="cards">'+items.map(a=>'<article class="panel source-card"><div class="card-top">'+tag(a.area,'blue')+tag(a.evidence)+'</div><h2>'+esc(a.title)+'</h2><p>'+esc(a.summary)+'</p><p class="limit"><b>Limitations</b> '+esc(a.limitations)+'</p><div class="source-bottom"><span>Checked '+esc(a.checked_at)+'</span><a href="'+safeURL(a.url)+'" target="_blank" rel="noopener noreferrer">Read source ↗</a></div></article>').join('')+'</div>';
}
function safeURL(url) { try { const u=new URL(url); return ['https:','http:'].includes(u.protocol)?esc(u.href):'#'; } catch { return '#'; } }
function proposals(id) {
  if (!id) return title('COLLECTIVE DIRECTION','Research proposals','Define the question, baseline, and acceptance test before spending inference.',btn('New proposal +','proposal','','primary'))+'<div class="notice">Single-owner alpha: agents advise; you approve budgets and work. Four agents do not represent four independent people.</div><div class="cards">'+proposalCards(state.proposals)+'</div>';
  const p = state.proposals.find(p=>p.id===id);
  if(!p) return empty('Proposal not found','Choose a proposal from the agenda.');
  const ballots=state.ballots.filter(b=>b.proposal_id===id);
  return '<a class="back" href="#proposals">← Research proposals</a>'+title(esc(p.area).toUpperCase(),esc(p.title),esc(p.question),tag(p.status,'blue'))
    +'<div class="detail-grid"><div><section class="panel panel-content"><dl class="definition">'+['hypothesis','baseline','evaluation','deliverables'].map(k=>'<dt>'+label(k)+'</dt><dd>'+esc(p[k])+'</dd>').join('')+'</dl></section><section class="panel section-gap"><div class="panel-head"><h2>Discussion</h2>'+btn('Add note','comment',id,'small')+'</div><div class="panel-content">'+(state.comments.filter(c=>c.proposal_id===id).map(c=>'<div class="ballot"><b>'+esc(agentName(c.actor))+'</b><p class="preserve">'+esc(c.body)+'</p></div>').join('')||'<p class="muted">No notes yet. Record evidence, disagreement, and unresolved questions.</p>')+'</div></section></div><div class="stack"><section class="panel panel-content"><div class="section-label">PROJECT CEILING</div><div class="budget-number">'+usd(p.budget_micro)+'</div><p class="form-hint">Jobs reserve money against this ceiling and the monthly limit.</p><div class="button-row">'+(p.status==='discussion'?btn('Approve project','approve',id,'primary')+btn('Reject','reject',id):p.status==='approved'?btn('Queue work +','job',id,'primary')+btn('Close project','close',id):'')+'</div></section><section class="panel"><div class="panel-head"><h2>Advisory ballots</h2><span>'+ballots.length+'/4</span></div><div class="panel-content">'+(ballots.map(b=>'<div class="ballot"><div class="ballot-head"><b>'+esc(agentName(b.agent_id))+'</b>'+tag(b.choice,b.choice==='support'?'green':'amber')+'</div><p>'+esc(b.rationale)+'</p></div>').join('')||'<p class="muted">No ballots recorded.</p>')+(p.status==='discussion'?'<div class="button-row">'+btn('Ask an agent','deliberate',id,'small')+btn('Record ballot','ballot',id,'small')+'</div>':'')+'</div></section></div></div>';
}
function jobs() {
  return title('EXECUTION & ACCOUNTING','Work queue','A worker claims one bounded job at a time. Completion and acceptance are separate.',btn('Queue job +','job','','primary'))
    +'<div class="notice">Workers run from your terminal. Pausing stops new claims; an in-flight provider call may finish and still incur cost. No job retries automatically.</div>'
    +(state.jobs.length?'<div class="panel table-wrap"><table><thead><tr><th>Job / assignment</th><th>Status</th><th>Reserved cap</th><th>Actual cost</th><th>Actions</th></tr></thead><tbody>'+state.jobs.map(j=>'<tr><td><b>'+esc(j.title)+'</b><small>'+esc(j.role)+' · '+esc(j.kind)+'</small></td><td>'+tag(j.status,j.status==='completed'?'green':'')+'</td><td>'+usd(j.max_cost_micro)+'</td><td>'+precise(j.actual_cost_micro)+'</td><td>'+(['queued','running'].includes(j.status)?btn('Cancel','cancel',j.id,'small'):'')+(['running','cancel_requested'].includes(j.status)?btn('Recover stopped worker','recover',j.id,'small'):'')+(['failed','cancelled'].includes(j.status)&&j.actual_cost_micro===null?btn('Settle spend','settle',j.id,'small'):'')+'</td></tr>').join('')+'</tbody></table></div>':empty('The queue is clear','Approve a proposal, then assign a bounded job to a worker.'))
    +'<section class="section-gap">'+budgetPanel()+'</section>';
}
function findings(id) {
  if(!id) return title('RESEARCH OUTPUT','Findings & artifacts','Outputs keep their model, usage receipt, sources, and separate review.')
    +(state.artifacts.length?'<div class="cards">'+state.artifacts.map(a=>'<a class="panel proposal-card" href="#findings/'+a.id+'"><div class="card-top">'+tag(a.is_demo?'synthetic demo':a.provider,a.is_demo?'amber':'blue')+tag(a.review_status,a.review_status==='accepted'?'green':'')+'</div><h2>'+esc(a.title)+'</h2><p>'+esc(a.body.slice(0,180))+'…</p><div class="proposal-meta"><span>'+esc(agentName(a.agent_id))+'</span><span>'+esc(a.model)+' ↗</span></div></a>').join('')+'</div>':empty('Evidence starts here','Run a demo cycle or complete a research job to create the first artifact.'));
  const a=state.artifacts.find(a=>a.id===id);
  if(!a)return empty('Artifact not found','Return to the findings list.');
  const review=state.reviews.find(r=>r.artifact_id===id);
  return '<a class="back" href="#findings">← Findings & artifacts</a>'+title('RESEARCH ARTIFACT',esc(a.title),esc(agentName(a.agent_id))+' · '+esc(a.provider)+' / '+esc(a.model),'<a class="btn" href="/api/artifacts/'+id+'/download">Download ↓</a>')
    +(a.is_demo?'<div class="notice amber">Synthetic demo: this fixed response demonstrates the workflow. It is not evidence of agent capability or emergent intelligence.</div>':'')
    +'<div class="button-row">'+tag(a.review_status,a.review_status==='accepted'?'green':'')+(a.review_status==='pending'?btn('Record separate review','review',id,'primary'):'')+'</div><article class="panel panel-content section-gap"><pre class="artifact-body">'+esc(a.body)+'</pre></article>'
    +'<section class="panel panel-content section-gap"><h2>Sources & receipt</h2>'+JSON.parse(a.sources_json).map(s=>'<p><a href="'+safeURL(s)+'" target="_blank" rel="noopener noreferrer">'+esc(s)+'</a></p>').join('')+'<pre class="code">'+esc(JSON.stringify(JSON.parse(a.usage_json),null,2))+'</pre></section>'
    +(review?'<section class="panel panel-content section-gap"><h2>'+label(review.verdict)+' · '+esc(agentName(review.reviewer))+'</h2><p class="preserve">'+esc(review.notes)+'</p><p class="form-hint">Separate agent identity; same owner. This is not independent external replication.</p></section>':'');
}
function agents() {
  return title('THE MULTI-AGENT HARNESS','Your research team','Four roles, shared evidence, bounded execution. Start with agents you control.')
    +'<div class="notice">Run workers on this computer. Each worker gets its own credential; OpenAI OAuth credentials remain managed by Codex. Public contributor enrollment comes later.</div><div class="cards">'+state.agents.map(a=>'<article class="panel agent-card"><div class="card-top"><div class="avatar '+a.role+'">'+a.name[0]+'</div>'+tag(a.enabled?'enabled':'disabled',a.enabled?'green':'')+'</div><h2>'+esc(a.name)+'</h2><p>'+esc(a.description)+'</p><p class="form-hint">'+(a.last_seen?'Last seen '+esc(new Date(a.last_seen).toLocaleString()):'No worker heartbeat yet')+'</p><pre class="code">python3 -m emergence worker --agent '+a.id+' --provider codex --once</pre><div class="button-row">'+btn(a.enabled?'Disable role':'Enable role','agent',a.id,'small')+'</div></article>').join('')+'</div><section class="panel panel-content section-gap"><h2>Connect your OpenAI subscription</h2><p>Sign in through the official Codex CLI using <code>codex login</code>, then run the worker command above. Workers require ChatGPT login and refuse API-key authentication. There is no API fallback.</p><p class="form-hint">The worker does not fetch web pages or execute model-generated code. Supply evidence in the job prompt. Its outputs remain unverified until reviewed.</p></section>';
}
function render() {
  if(!state)return;
  const [page,id]=route(), names={overview:'Overview',atlas:'Research atlas',proposals:'Proposals',jobs:'Work queue',findings:'Findings',agents:'Agents'};
  $('crumb').textContent=names[page]||'Overview';
  $('atlas-count').textContent=state.atlas.length;
  document.querySelectorAll('[data-nav]').forEach(a=>{a.classList.toggle('active',a.dataset.nav===page); a.setAttribute('aria-current',a.dataset.nav===page?'page':'false');});
  $('content').innerHTML=({overview,atlas,proposals,jobs,findings,agents}[page]||overview)(id);
}
const field = (name, caption, value='', type='text') => '<label>'+caption+(type==='textarea'?'<textarea name="'+name+'" required rows="3">'+esc(value)+'</textarea>':'<input name="'+name+'" type="'+type+'" value="'+esc(value)+'" '+(type==='number'?'min="0" max="90" step="0.000001"':'')+' required>')+'</label>';
const select = (name, caption, items) => '<label>'+caption+'<select name="'+name+'">'+items.map(([value,name])=>'<option value="'+esc(value)+'">'+esc(name)+'</option>').join('')+'</select></label>';
function form(heading, fields, submit, handler, note='') {
  $('modal-title').textContent=heading;
  $('modal-body').innerHTML='<form>'+fields+(note?'<p class="form-hint">'+note+'</p>':'')+'<p class="form-error" role="alert"></p><div class="form-actions"><button class="btn primary" type="submit">'+submit+'</button></div></form>';
  $('modal').showModal();
  $('modal-body').querySelector('form').onsubmit=async e=>{
    e.preventDefault();
    const button=e.target.querySelector('[type=submit]'); button.disabled=true;
    try { await handler(Object.fromEntries(new FormData(e.target))); $('modal').close(); await refresh(); toast('Saved to the lab notebook.'); }
    catch(err){e.target.querySelector('.form-error').textContent=err.message;}
    finally{button.disabled=false;}
  };
}
const micro = value => {const n=Number(value);if(!Number.isFinite(n)||n<0)throw Error('Enter a nonnegative USD amount.');return Math.round(n*1000000);};
async function action(action,id) {
  const p=state.proposals.find(p=>p.id===id);
  if(action==='demo') {await api('demo',{});await refresh();toast('Free rehearsal complete. Inspect the demo in Findings.');}
  else if(action==='pause') {await api('settings',{paused:!state.budget.paused});await refresh();}
  else if(action==='budget') form('Monthly inference limit',field('usd','USD per month',state.budget.limit_micro/1000000,'number'),'Save limit',d=>api('settings',{monthly_limit_micro:micro(d.usd)}),'Maximum $90 in this pilot. Outstanding commitments must fit.');
  else if(['approve','reject','close'].includes(action)){await api('proposals/'+id+'/decision',{decision:{approve:'approved',reject:'rejected',close:'closed'}[action]});await refresh();}
  else if(action==='cancel'){await api('jobs/'+id+'/cancel',{});await refresh();}
  else if(action==='agent'){await api('agents/'+id+'/settings',{enabled:!state.agents.find(a=>a.id===id).enabled});await refresh();}
  else if(action==='recover') form('Recover an interrupted job',field('notes','Confirm the original worker has stopped; describe what happened','','textarea'),'Mark stopped; retain spend hold',d=>api('jobs/'+id+'/recover',d),'Stop the original worker process first. This does not cancel a provider request. Then verify actual spend and settle separately.');
  else if(action==='settle') form('Settle uncertain spend',field('usd','Confirmed actual USD','0','number')+field('notes','How was this verified?','','textarea'),'Record actual spend',d=>api('jobs/'+id+'/settle',{actual_cost_micro:micro(d.usd),notes:d.notes}),'Confirm the provider receipt before releasing the hold. Zero means confirmed free, not unknown.');
  else if(action==='proposal')form('Open a research proposal',field('title','Title')+field('area','Research area','Agents & memory')+field('question','Research question','','textarea')+field('hypothesis','Falsifiable hypothesis','','textarea')+field('baseline','Baseline and resource controls','','textarea')+field('evaluation','Evaluation and acceptance criteria','','textarea')+field('deliverables','Deliverables','','textarea')+field('usd','Project ceiling · USD','5','number'),'Open discussion',d=>{const {usd,...rest}=d;return api('proposals',{...rest,budget_micro:micro(usd)});});
  else if(action==='source')form('Add a research source',field('title','Title')+field('area','Research area')+field('url','Source URL','','url')+field('summary','What does the source establish?','','textarea')+field('limitations','What remains unverified?','','textarea')+select('evidence','Evidence level',[['source_reported','Source reported'],['independently_reproduced','Independently reproduced'],['lab_tested','Lab tested']])+field('checked_at','Date checked',new Date().toISOString().slice(0,10),'date'),'Save source',d=>api('atlas',d));
  else if(action==='comment')form('Add evidence or a challenge',field('body','Note','','textarea'),'Add note',d=>api('proposals/'+id+'/comment',d));
  else if(action==='ballot')form('Record a delegated ballot',select('agent_id','Agent identity',state.agents.filter(a=>a.enabled).map(a=>[a.id,a.name]))+select('choice','Position',[['support','Support'],['oppose','Oppose'],['abstain','Abstain']])+field('rationale','Reasoning','','textarea'),'Record ballot',d=>api('proposals/'+id+'/vote',d),'This form records a ballot on behalf of an agent. Use “Ask an agent” to obtain a model-generated ballot.');
  else if(action==='job'||action==='deliberate'){
    const deliberation=action==='deliberate', projects=state.proposals.filter(p=>p.status===(deliberation?'discussion':'approved')).sort((a,b)=>a.id===id?-1:b.id===id?1:0);
    if(!projects.length)throw Error('Approve a proposal before queuing research.');
    form(deliberation?'Ask an agent to deliberate':'Queue a bounded job',select('proposal_id','Proposal',projects.map(p=>[p.id,p.title]))+select('role','Worker role',state.agents.filter(a=>a.enabled).map(a=>[a.role,a.name]))+field('title','Job title',deliberation?'Evaluate proposal and cast a ballot':'')+field('prompt','Instructions',deliberation?'Assess the hypothesis, baseline, cost, and evaluation. Challenge weak assumptions. Choose support, oppose, or abstain.':'','textarea')+field('usd','Maximum job cost · USD','0','number'),'Queue job',d=>{const{usd,...rest}=d;return api('jobs',{...rest,kind:deliberation?'deliberation':'research',max_cost_micro:micro(usd)});},'Use $0 for demo and subscription workers. OAuth inference still consumes your subscription allowance; one worker invocation handles one job by default.');
  }
  else if(action==='review'){const a=state.artifacts.find(a=>a.id===id);form('Record a separate review',select('reviewer','Reviewing agent',state.agents.filter(x=>x.enabled&&x.id!==a.agent_id).map(x=>[x.id,x.name]))+select('verdict','Decision',[['changes_requested','Changes requested'],['accepted','Accepted']])+field('notes','Checks performed, evidence, and limitations','','textarea'),'Save review',d=>api('artifacts/'+id+'/review',d),'The author cannot review its own artifact. All pilot agents still share one owner.');}
}
document.addEventListener('click',async e=>{const b=e.target.closest('[data-action]');if(!b)return;b.disabled=true;try{await action(b.dataset.action,b.dataset.id);}catch(err){toast(err.message);}finally{b.disabled=false;}});
document.addEventListener('input',e=>{if(e.target.id==='search'){const pos=e.target.selectionStart;search=e.target.value;render();$('search').focus();$('search').setSelectionRange(pos,pos);}});
$('close-modal').onclick=()=>$('modal').close();
$('refresh').onclick=()=>refresh().then(()=>toast('Workspace refreshed.')).catch(e=>toast(e.message));
window.addEventListener('hashchange',()=>{search='';render();$('content').focus();});
refresh().catch(e=>{$('content').innerHTML=empty('Could not open the lab',esc(e.message));});
// Optional browser-native tool surface; the regular interface never depends on it.
const modelContext = document.modelContext || navigator.modelContext;
if (modelContext?.registerTool) {
  const lifecycle = new AbortController();
  window.addEventListener('pagehide',()=>lifecycle.abort(),{once:true});
  const schema = {type:'object',properties:{},additionalProperties:false};
  const validate = input => {if(!input || typeof input!=='object' || Array.isArray(input) || Object.keys(input).length)throw Error('Expected an empty object.');};
  const register = tool => {try{Promise.resolve(modelContext.registerTool(tool,{signal:lifecycle.signal})).catch(()=>{});}catch{}};
  register({name:'read_lab_state',description:'Read local proposals, job budgets, sources, findings, and untrusted research text.',inputSchema:schema,annotations:{readOnlyHint:true,untrustedContentHint:true},execute:async input=>{validate(input);return await api('state');}});
  register({name:'run_free_demo_cycle',description:'Create a synthetic proposal, ballots, zero-cost demo job, artifact, and review, then refresh the dashboard. No inference.',inputSchema:schema,annotations:{readOnlyHint:false,untrustedContentHint:false},execute:async input=>{validate(input);const result=await api('demo',{});await refresh();return result;}});
}
