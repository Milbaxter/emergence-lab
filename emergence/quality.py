"""Versioned reader-facing reports; evidence and editorial readiness stay separate."""
import hashlib
import html
import json
from .db import LabError, now, uid

BRIEF_FIELDS = ('audience', 'decision', 'need', 'difference')
REPORT_LIMITS = {'title':120, 'takeaway':400, 'audience':240, 'why_it_matters':800,
                 'what_was_tested':1200, 'result':1600, 'what_to_do':1000,
                 'limitations':1000, 'next_step':600}
CRITERIA = ('usefulness', 'evidence', 'clarity', 'actionability', 'restraint')

def object_schema(fields):
    return {'type':'object','properties':{k:{'type':'string'} for k in fields},
            'required':list(fields),'additionalProperties':False}

FIELDS = {
    'brief': object_schema(BRIEF_FIELDS),
    'report': {'type':'object','properties':{
        **{k:{'type':'string'} for k in REPORT_LIMITS},
        'evidence_ids':{'type':'array','items':{'type':'string'}}},
        'required':[*REPORT_LIMITS,'evidence_ids'],'additionalProperties':False},
    'checks': {'type':'array','items':{'type':'object','properties':{
        'criterion':{'type':'string','enum':list(CRITERIA)}, 'passed':{'type':'boolean'},
        'reason':{'type':'string'},'field':{'type':'string'},'quote':{'type':'string'},'evidence_id':{'type':'string'}},
        'required':['criterion','passed','reason','field','quote','evidence_id'],'additionalProperties':False}}
}

def validate_fields(response):
    brief=response['brief'];report=response['report'];checks=response['checks']
    if not isinstance(brief,dict) or set(brief)!=set(BRIEF_FIELDS):
        raise ValueError('Invalid reader brief.')
    if any(not isinstance(v,str) or len(v)>1200 for v in brief.values()):
        raise ValueError('Reader brief fields must be concise strings.')
    if not isinstance(report,dict) or set(report)!={*REPORT_LIMITS,'evidence_ids'}:
        raise ValueError('Invalid human report.')
    if any(not isinstance(report[k],str) or len(report[k])>limit for k,limit in REPORT_LIMITS.items()):
        raise ValueError('Report field is oversized or not text.')
    if (not isinstance(report['evidence_ids'],list) or len(report['evidence_ids'])>4
        or any(not isinstance(x,str) or len(x)>100 for x in report['evidence_ids'])):
        raise ValueError('Invalid report evidence references.')
    if not isinstance(checks,list) or len(checks)>5:
        raise ValueError('Invalid quality checks.')
    seen=set()
    for c in checks:
        if (not isinstance(c,dict) or set(c)!={'criterion','passed','reason','field','quote','evidence_id'}
            or c['criterion'] not in CRITERIA or c['criterion'] in seen
            or type(c['passed']) is not bool or not isinstance(c['reason'],str)
            or not 1<=len(c['reason'])<=1500):
            raise ValueError('Quality checks need distinct criteria and specific reasons.')
        if any(not isinstance(c[k],str) or len(c[k])>limit for k,limit in [('field',100),('quote',400),('evidence_id',100)]):
            raise ValueError('Quality checks must name fields, quote passages, and reference bounded evidence IDs.')
        seen.add(c['criterion'])

def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS mission_reports(
      id TEXT PRIMARY KEY,mission_id TEXT NOT NULL REFERENCES missions(id),claim_id TEXT NOT NULL REFERENCES mission_claims(id),
      status TEXT NOT NULL,current_version TEXT,reason TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS mission_report_versions(
      id TEXT PRIMARY KEY,report_id TEXT NOT NULL REFERENCES mission_reports(id),turn_id TEXT NOT NULL,
      content_json TEXT NOT NULL,content_sha256 TEXT NOT NULL,created_at TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS mission_report_reviews(
      id TEXT PRIMARY KEY,report_id TEXT NOT NULL REFERENCES mission_reports(id),version_id TEXT NOT NULL,
      turn_id TEXT NOT NULL,verdict TEXT NOT NULL,checks_json TEXT NOT NULL,notes TEXT NOT NULL,created_at TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS mission_report_feedback(
      report_id TEXT PRIMARY KEY REFERENCES mission_reports(id),value TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL)''')

def feedback(db,identifier,value,reason):
    if value not in {'useful','not_useful'} or not isinstance(reason,str) or not 1<=len(reason.strip())<=1500:
        raise LabError('Choose useful or not useful and give a short reason.')
    if not db.execute('SELECT 1 FROM mission_reports WHERE id=?',(identifier,)).fetchone():
        raise LabError('Report not found.',404)
    db.execute('INSERT INTO mission_report_feedback VALUES(?,?,?,?) ON CONFLICT(report_id) DO UPDATE SET value=excluded.value,reason=excluded.reason,created_at=excluded.created_at',
               (identifier,value,reason.strip(),now()))
    return {'ok':True}

def evidence_ids(claim):
    return [e['run_id'] for e in json.loads(claim['evidence_json']) if e.get('run_id')]

def report_issues(report,claim):
    issues=[]
    for key in REPORT_LIMITS:
        if not report[key].strip():
            issues.append('Missing '+key.replace('_',' ')+'.')
    words=sum(len(report[k].split()) for k in REPORT_LIMITS)
    if words>650:
        issues.append('Reduce the report to at most 650 words.')
    if set(report['evidence_ids'])!=set(evidence_ids(claim)):
        issues.append('Reference exactly the experiment and verification supporting this claim.')
    if claim['status']!='peer_checked':
        issues.append('The underlying finding has not passed evidence review.')
    return issues

def save_draft(db,mission,ctx,turn,response):
    report=response['report']
    claim=dict(db.execute('SELECT * FROM mission_claims WHERE id=?',(ctx['claim_id'],)).fetchone())
    rid=ctx.get('report_id') or uid('report')
    if not ctx.get('report_id'):
        db.execute('INSERT INTO mission_reports VALUES(?,?,?,?,?,?,?,?)',
                   (rid,mission['id'],claim['id'],'draft',None,'Awaiting reader review.',now(),now()))
    version=uid('edition')
    encoded=json.dumps(report,ensure_ascii=False,sort_keys=True)
    db.execute('INSERT INTO mission_report_versions VALUES(?,?,?,?,?,?)',
               (version,rid,turn['id'],encoded,hashlib.sha256(encoded.encode()).hexdigest(),now()))
    db.execute("UPDATE mission_reports SET status='draft',current_version=?,reason='Awaiting review of this exact edition.',updated_at=? WHERE id=?",(version,now(),rid))
    ctx.update(report_id=rid,stage='read',report_issues=report_issues(report,claim))

def review_draft(db,mission,ctx,turn,response,remaining):
    row=db.execute('''SELECT r.*,v.content_json,v.content_sha256 FROM mission_reports r
        JOIN mission_report_versions v ON r.current_version=v.id WHERE r.id=?''',(ctx['report_id'],)).fetchone()
    claim=dict(db.execute('SELECT * FROM mission_claims WHERE id=?',(row['claim_id'],)).fetchone())
    issues=report_issues(json.loads(row['content_json']),claim)
    if ctx.get('revision_original_hash')==row['content_sha256']:
        issues.append('The draft is unchanged after a blocking review; revision must address the defects.')
    checks=response['checks']
    if {c['criterion'] for c in checks}!=set(CRITERIA):
        issues.append('The reader must check usefulness, evidence, clarity, actionability, and restraint.')
    issues.extend(c['criterion']+': '+c['reason'] for c in checks if not c['passed'])
    content=json.loads(row['content_json'])
    reasons=set()
    for c in checks:
        if (c['field'] not in REPORT_LIMITS or len(c['quote'].strip())<12
            or c['quote'] not in content.get(c['field'],'') or len(c['reason'].strip())<40):
            issues.append(c['criterion']+': cite a real report field and passage, with a specific explanation.')
        if c['reason'].strip().lower() in reasons:
            issues.append('Each criterion needs its own explanation, not repeated boilerplate.')
        reasons.add(c['reason'].strip().lower())
        if c['criterion']=='evidence' and c['evidence_id'] not in evidence_ids(claim):
            issues.append('The evidence check must reference a supporting run ID.')
    approved=response['verdict']=='accept' and not issues
    db.execute('INSERT INTO mission_report_reviews VALUES(?,?,?,?,?,?,?,?)',
               (uid('edit_review'),row['id'],row['current_version'],turn['id'],
                'accept' if approved else 'revise',json.dumps(checks),response['message'],now()))
    can_revise=not approved and response['verdict']!='reject' and ctx.get('editorial_revision',0)<1 and remaining>=2
    status='ready' if approved else ('changes_requested' if can_revise else 'withheld')
    reason='All five reader checks passed for this edition.' if approved else '\n'.join(issues or [response['message'] or 'Reader did not accept this edition.'])
    db.execute('UPDATE mission_reports SET status=?,reason=?,updated_at=? WHERE id=?',(status,reason,now(),row['id']))
    ctx['quality_notes']=reason
    if can_revise:
        ctx.update(stage='write',editorial_revision=ctx.get('editorial_revision',0)+1,revision_original_hash=row['content_sha256'])
    return status

def reports(db,mission_id):
    return [dict(r) for r in db.execute('''SELECT r.*,v.content_json,v.content_sha256,f.value AS reader_feedback,f.reason AS feedback_reason
        FROM mission_reports r LEFT JOIN mission_report_versions v ON r.current_version=v.id
        LEFT JOIN mission_report_feedback f ON f.report_id=r.id
        WHERE r.mission_id=? ORDER BY r.rowid DESC''',(mission_id,))]

def download(db,identifier):
    row=db.execute('''SELECT r.*,v.content_json,v.content_sha256,c.status AS evidence_status,m.provider
        FROM mission_reports r JOIN mission_report_versions v ON r.current_version=v.id
        JOIN mission_claims c ON r.claim_id=c.id JOIN missions m ON r.mission_id=m.id WHERE r.id=?''',(identifier,)).fetchone()
    if not row:
        raise LabError('Report not found.',404)
    if row['status']!='ready' or row['evidence_status']!='peer_checked':
        raise LabError('This edition has not passed all checks or its evidence was withdrawn.',409)
    report=json.loads(row['content_json']);esc=html.escape
    sections=''.join('<section><h2>'+label+'</h2><p>'+esc(report[key])+'</p></section>' for key,label in (
        ('why_it_matters','Why it matters'),('what_was_tested','What was tested'),('result','What we found'),
        ('what_to_do','What you can do'),('limitations','Where this stops'),('next_step','The next useful step')))
    demo='SYNTHETIC REHEARSAL · ' if row['provider']=='demo' else ''
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>'+esc(report['title'])+'</title><style>'
        'body{margin:0;background:#f1f3ee;color:#1f3027;font:17px/1.7 system-ui,sans-serif}main{max-width:800px;margin:48px auto;padding:48px;background:#fff;border:1px solid #dce4d9;border-radius:16px}'
        'h1{font:600 42px/1.15 Georgia,serif;letter-spacing:-1px;margin:18px 0 24px}h2{font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#4e6656;margin-top:32px}p{white-space:pre-wrap;overflow-wrap:anywhere}'
        '.takeaway{font-size:22px;line-height:1.5;border-left:3px solid #75955d;padding-left:20px}.meta,footer{font-size:12px;color:#58695e}footer{border-top:1px solid #dde4da;margin-top:36px;padding-top:20px;overflow-wrap:anywhere}'
        '@media(max-width:600px){main{margin:0;padding:26px;border:0;border-radius:0}h1{font-size:32px}}@media print{body{background:white}main{margin:0;border:0;padding:0}section{break-inside:avoid}}</style>'
        '<main><div class="meta">'+demo+'EMERGENCE LAB · REVIEWED RESEARCH NOTE</div><h1>'+esc(report['title'])+'</h1>'
        '<p class="takeaway">'+esc(report['takeaway'])+'</p><p class="meta">For '+esc(report['audience'])+'</p>'+sections+
        '<footer>Evidence: '+esc(', '.join(report['evidence_ids']))+'<br>Edition: '+esc(row['current_version'])+
        '<br>SHA-256: '+esc(row['content_sha256'])+'<br>Agent-reviewed. Human usefulness and independent replication remain unverified.</footer></main></html>').encode()
