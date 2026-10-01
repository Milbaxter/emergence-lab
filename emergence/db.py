"""SQLite state machine. Money is integer USD microdollars, never floats."""
from __future__ import annotations
import contextlib
import datetime as dt
import hashlib
import json
import secrets
import sqlite3
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from .seed import AGENTS, ATLAS

MICRO = 1_000_000
ROLES = {a[2] for a in AGENTS}

class LabError(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def month():
    return now()[:7]

def uid(prefix):
    return prefix + "_" + uuid.uuid4().hex[:12]

def text(value, field, limit=20_000, required=True):
    if not isinstance(value, str) or len(value) > limit:
        raise LabError(f"{field} must be text of at most {limit:,} characters.")
    value = value.strip()
    if required and not value:
        raise LabError(f"{field} is required.")
    return value

def money(value, field="Cost", limit=90 * MICRO):
    if type(value) is not int or not 0 <= value <= limit:
        raise LabError(f"{field} must be an integer between 0 and {limit} microdollars.")
    return value

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

class Lab:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / "lab.sqlite"
        self.initialize()

    @contextlib.contextmanager
    def tx(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS agents(
              id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, description TEXT NOT NULL,
              owner TEXT NOT NULL DEFAULT 'local-owner', enabled INTEGER NOT NULL DEFAULT 1,
              token_hash TEXT, last_seen TEXT);
            CREATE TABLE IF NOT EXISTS atlas(
              id TEXT PRIMARY KEY, area TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
              summary TEXT NOT NULL, limitations TEXT NOT NULL, evidence TEXT NOT NULL,
              checked_at TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS proposals(
              id TEXT PRIMARY KEY, title TEXT NOT NULL, area TEXT NOT NULL, question TEXT NOT NULL,
              hypothesis TEXT NOT NULL, baseline TEXT NOT NULL, evaluation TEXT NOT NULL,
              deliverables TEXT NOT NULL, budget_micro INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'discussion', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS comments(
              id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL REFERENCES proposals(id),
              actor TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ballots(
              proposal_id TEXT NOT NULL REFERENCES proposals(id), agent_id TEXT NOT NULL REFERENCES agents(id),
              choice TEXT NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL,
              PRIMARY KEY(proposal_id,agent_id));
            CREATE TABLE IF NOT EXISTS jobs(
              id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL REFERENCES proposals(id),
              title TEXT NOT NULL, role TEXT NOT NULL, kind TEXT NOT NULL, prompt TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'queued', max_cost_micro INTEGER NOT NULL,
              actual_cost_micro INTEGER, settled_month TEXT, allocation_month TEXT NOT NULL,
              agent_id TEXT REFERENCES agents(id), claim_hash TEXT, claimed_at TEXT,
              heartbeat_at TEXT, completion_hash TEXT, completion_json TEXT, receipt_json TEXT,
              created_at TEXT NOT NULL, finished_at TEXT);
            CREATE TABLE IF NOT EXISTS artifacts(
              id TEXT PRIMARY KEY, job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
              agent_id TEXT NOT NULL REFERENCES agents(id), title TEXT NOT NULL,
              body TEXT NOT NULL, sources_json TEXT NOT NULL, usage_json TEXT NOT NULL,
              provider TEXT NOT NULL, model TEXT NOT NULL, is_demo INTEGER NOT NULL,
              review_status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reviews(
              id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL UNIQUE REFERENCES artifacts(id),
              reviewer TEXT NOT NULL REFERENCES agents(id), verdict TEXT NOT NULL,
              notes TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
              id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
              actor TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_jobs_status_role ON jobs(status,role,created_at);
            CREATE INDEX IF NOT EXISTS idx_jobs_proposal ON jobs(proposal_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_month ON jobs(settled_month);
            CREATE INDEX IF NOT EXISTS idx_comments_proposal ON comments(proposal_id);
            """)
        with self.tx() as db:
            if "receipt_json" not in {r[1] for r in db.execute("PRAGMA table_info(jobs)")}:
                db.execute("ALTER TABLE jobs ADD COLUMN receipt_json TEXT")
            db.execute("INSERT OR IGNORE INTO settings VALUES('monthly_limit_micro','90000000')")
            db.execute("INSERT OR IGNORE INTO settings VALUES('paused','false')")
            for aid, name, role, description in AGENTS:
                db.execute("INSERT OR IGNORE INTO agents(id,name,role,description) VALUES(?,?,?,?)",
                           (aid, name, role, description))
            if not db.execute("SELECT 1 FROM settings WHERE key='seeded'").fetchone():
                for area, title, url, summary, limits in ATLAS:
                    db.execute("INSERT INTO atlas VALUES(?,?,?,?,?,?,?,?,?)",
                               (uid("source"), area, title, url, summary, limits, "source_reported",
                                "2026-10-01", now()))
                db.execute("INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
                    "proposal_first", "Does shared memory improve a research team?",
                    "Agents & memory", "Can a persistent shared evidence notebook improve performance per unit of inference?",
                    "A shared notebook reduces repeated mistakes on fresh tasks.",
                    "One agent and independent attempts with the same model and total resource budget.",
                    "Freeze model versions, compare held-out tasks, log all calls, and report quality, cost and latency separately.",
                    "Runnable protocol, raw measurements, limitations, and a second-agent replication report.",
                    5 * MICRO, "discussion", now()))
                db.execute("INSERT INTO settings VALUES('seeded','true')")
                self.event(db, "created", "owner", "Lab initialized. No inference has been run.")

    @staticmethod
    def event(db, kind, actor, message):
        db.execute("INSERT INTO events(kind,actor,message,created_at) VALUES(?,?,?,?)",
                   (kind, actor, message, now()))

    @staticmethod
    def row(db, table, identifier):
        if table not in {"agents", "proposals", "jobs", "artifacts"}:
            raise ValueError("Invalid table")
        item = db.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)).fetchone()
        if not item:
            raise LabError(f"{table[:-1].capitalize()} not found.", 404)
        return dict(item)

    def budget(self, db):
        cap = int(db.execute("SELECT value FROM settings WHERE key='monthly_limit_micro'").fetchone()[0])
        spent = db.execute("SELECT COALESCE(SUM(actual_cost_micro),0) FROM jobs WHERE settled_month=?", (month(),)).fetchone()[0]
        held = db.execute("SELECT COALESCE(SUM(max_cost_micro),0) FROM jobs WHERE actual_cost_micro IS NULL").fetchone()[0]
        return {"limit_micro": cap, "spent_micro": spent, "reserved_micro": held,
                "available_micro": cap - spent - held, "month": month(),
                "paused": db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0] == "true"}

    def state(self):
        with self.tx() as db:
            agents = [dict(r) for r in db.execute("SELECT id,name,role,description,owner,enabled,last_seen,token_hash IS NOT NULL AS connected FROM agents")]
            jobs = [dict(r) for r in db.execute("""SELECT id,proposal_id,title,role,kind,prompt,status,
                     max_cost_micro,actual_cost_micro,agent_id,created_at,claimed_at,heartbeat_at,finished_at,receipt_json
                     FROM jobs ORDER BY created_at DESC""")]
            return {
                "version": "0.1.0", "budget": self.budget(db), "agents": agents, "jobs": jobs,
                **{table: [dict(r) for r in db.execute(f"SELECT * FROM {table} ORDER BY created_at DESC")]
                   for table in ["atlas", "proposals", "comments", "ballots", "artifacts", "reviews"]},
                "events": [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 60")],
            }

    def settings(self, payload):
        with self.tx() as db:
            if "paused" in payload:
                if type(payload["paused"]) is not bool:
                    raise LabError("paused must be a boolean.")
                if not payload["paused"] and self.budget(db)["available_micro"] < 0:
                    raise LabError("Cancel queued obligations until recorded spend and holds fit the limit.", 409)
                db.execute("UPDATE settings SET value=? WHERE key='paused'", (json.dumps(payload["paused"]),))
                self.event(db, "settings", "owner", "Job claims paused." if payload["paused"] else "Job claims resumed.")
            if "monthly_limit_micro" in payload:
                cap = money(payload["monthly_limit_micro"], "Monthly limit")
                b = self.budget(db)
                if cap < b["spent_micro"] + b["reserved_micro"]:
                    raise LabError("The limit cannot be below recorded spend plus outstanding reservations.")
                db.execute("UPDATE settings SET value=? WHERE key='monthly_limit_micro'", (str(cap),))
                self.event(db, "settings", "owner", f"Monthly limit set to USD {cap / MICRO:.2f}.")
        return {"ok": True}

    def add_atlas(self, p):
        vals = [text(p.get(k), k, 4000 if k in {"summary", "limitations"} else 400)
                for k in ["area", "title", "url", "summary", "limitations"]]
        parsed = urlsplit(vals[2])
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username:
            raise LabError("Use a valid public http(s) source URL.")
        evidence = p.get("evidence", "source_reported")
        if evidence not in {"source_reported", "independently_reproduced", "lab_tested"}:
            raise LabError("Invalid evidence level.")
        checked = text(p.get("checked_at", now()[:10]), "checked_at", 10)
        try:
            dt.date.fromisoformat(checked)
        except ValueError:
            raise LabError("Use a YYYY-MM-DD source-check date.") from None
        identifier = uid("source")
        with self.tx() as db:
            db.execute("INSERT INTO atlas VALUES(?,?,?,?,?,?,?,?,?)",
                       (identifier, *vals, evidence, checked, now()))
            self.event(db, "source", "owner", f"Added source: {vals[1]}")
        return {"id": identifier}

    def proposal(self, p):
        fields = ["title", "area", "question", "hypothesis", "baseline", "evaluation", "deliverables"]
        values = [text(p.get(k), k, 500 if k in {"title", "area"} else 6000) for k in fields]
        budget = money(p.get("budget_micro"), "Project limit")
        identifier = uid("proposal")
        with self.tx() as db:
            db.execute("INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (identifier, *values, budget, "discussion", now()))
            self.event(db, "proposal", "owner", f"Opened proposal: {values[0]}")
        return {"id": identifier}

    def comment(self, identifier, p, actor="owner"):
        body = text(p.get("body"), "Comment", 10_000)
        with self.tx() as db:
            self.row(db, "proposals", identifier)
            db.execute("INSERT INTO comments VALUES(?,?,?,?,?)", (uid("comment"), identifier, actor, body, now()))
            self.event(db, "discussion", actor, "Added evidence to a proposal.")
        return {"ok": True}

    def vote(self, identifier, p, actor):
        choice = p.get("choice")
        if choice not in {"support", "oppose", "abstain"}:
            raise LabError("Choose support, oppose or abstain.")
        rationale = text(p.get("rationale"), "Rationale", 4000)
        with self.tx() as db:
            proposal = self.row(db, "proposals", identifier)
            agent = self.row(db, "agents", actor)
            if proposal["status"] != "discussion" or not agent["enabled"]:
                raise LabError("Voting is closed or this agent is disabled.", 409)
            db.execute("""INSERT INTO ballots VALUES(?,?,?,?,?) ON CONFLICT(proposal_id,agent_id)
                          DO UPDATE SET choice=excluded.choice,rationale=excluded.rationale,created_at=excluded.created_at""",
                       (identifier, actor, choice, rationale, now()))
            self.event(db, "vote", actor, f"Recorded {choice} ballot.")
        return {"ok": True}

    def decide(self, identifier, p):
        decision = p.get("decision")
        if decision not in {"approved", "rejected", "closed"}:
            raise LabError("Invalid decision.")
        with self.tx() as db:
            proposal = self.row(db, "proposals", identifier)
            if proposal["status"] == decision:
                return {"ok": True}
            if decision == "closed":
                if proposal["status"] != "approved":
                    raise LabError("Only an approved project can be closed.", 409)
                if db.execute("SELECT 1 FROM jobs WHERE proposal_id=? AND actual_cost_micro IS NULL", (identifier,)).fetchone():
                    raise LabError("Settle or cancel all jobs before closing the project.", 409)
            elif proposal["status"] != "discussion":
                raise LabError("This proposal has already been decided.", 409)
            db.execute("UPDATE proposals SET status=? WHERE id=?", (decision, identifier))
            self.event(db, "decision", "owner", f"{proposal['title']}: {decision}. Ballots are advisory in this single-owner alpha.")
        return {"ok": True}

    def enqueue(self, p):
        identifier = uid("job")
        proposal_id = text(p.get("proposal_id"), "Proposal", 80)
        title = text(p.get("title"), "Title", 300)
        prompt = text(p.get("prompt"), "Instructions", 20_000)
        role = p.get("role", "researcher")
        kind = p.get("kind", "research")
        cap = money(p.get("max_cost_micro", 0), "Job limit")
        if role not in ROLES or kind not in {"research", "replication", "synthesis", "deliberation"}:
            raise LabError("Invalid role or job kind.")
        with self.tx() as db:
            prop = self.row(db, "proposals", proposal_id)
            b = self.budget(db)
            expected = "discussion" if kind == "deliberation" else "approved"
            if prop["status"] != expected:
                raise LabError("Deliberate on an open discussion, or approve the proposal before research.", 409)
            if b["paused"] or b["available_micro"] < cap:
                raise LabError("Paused or insufficient monthly budget.", 409)
            committed = db.execute("SELECT COALESCE(SUM(COALESCE(actual_cost_micro,max_cost_micro)),0) FROM jobs WHERE proposal_id=?",
                                   (proposal_id,)).fetchone()[0]
            if committed + cap > prop["budget_micro"]:
                raise LabError("This job exceeds the remaining project limit.", 409)
            db.execute("""INSERT INTO jobs(id,proposal_id,title,role,kind,prompt,max_cost_micro,allocation_month,created_at)
                          VALUES(?,?,?,?,?,?,?,?,?)""",
                       (identifier, proposal_id, title, role, kind, prompt, cap, month(), now()))
            self.event(db, "queued", "owner", f"Queued {title}; reserved USD {cap / MICRO:.2f}.")
        return {"id": identifier}

    def issue_token(self, identifier):
        token = secrets.token_urlsafe(32)
        with self.tx() as db:
            self.row(db, "agents", identifier)
            if db.execute("SELECT 1 FROM jobs WHERE agent_id=? AND status IN ('running','cancel_requested')", (identifier,)).fetchone():
                raise LabError("Wait for active jobs to settle before rotating this agent's token.", 409)
            db.execute("UPDATE agents SET token_hash=? WHERE id=?", (digest(token), identifier))
            self.event(db, "worker", "owner", f"Worker credential issued for {identifier}.")
        return token

    def authenticate(self, token):
        with self.tx() as db:
            row = db.execute("SELECT * FROM agents WHERE token_hash=? AND enabled=1", (digest(token),)).fetchone()
            if not row:
                raise LabError("Invalid worker credential.", 401)
            return dict(row)

    def claim(self, agent_id, max_job_micro=90 * MICRO, job_id=None):
        money(max_job_micro, "Worker per-job limit")
        claim_token = secrets.token_urlsafe(32)
        with self.tx() as db:
            agent = self.row(db, "agents", agent_id)
            if not agent["enabled"] or self.budget(db)["paused"] or self.budget(db)["available_micro"] < 0:
                return {"job": None}
            if db.execute("SELECT 1 FROM jobs WHERE agent_id=? AND status IN ('running','cancel_requested')", (agent_id,)).fetchone():
                return {"job": None}
            job = db.execute("""SELECT jobs.* FROM jobs JOIN proposals ON proposals.id=jobs.proposal_id
                             WHERE jobs.status='queued' AND jobs.role=? AND jobs.max_cost_micro<=?
                             AND ((jobs.kind='deliberation' AND proposals.status='discussion') OR (jobs.kind!='deliberation' AND proposals.status='approved'))
                             AND (? IS NULL OR jobs.id=?) ORDER BY jobs.created_at LIMIT 1""",
                             (agent["role"], max_job_micro, job_id, job_id)).fetchone()
            db.execute("UPDATE agents SET last_seen=? WHERE id=?", (now(), agent_id))
            if not job:
                return {"job": None}
            db.execute("UPDATE jobs SET status='running',agent_id=?,claim_hash=?,claimed_at=?,heartbeat_at=? WHERE id=?",
                       (agent_id, digest(claim_token), now(), now(), job["id"]))
            proposal = self.row(db, "proposals", job["proposal_id"])
            self.event(db, "claimed", agent_id, f"Claimed {job['title']}.")
            result = dict(job)
            result.update({"status": "running", "agent_id": agent_id, "claim_token": claim_token, "proposal": proposal})
            for key in ["claim_hash", "completion_hash", "completion_json"]:
                result.pop(key, None)
        return {"job": result}

    @staticmethod
    def check_claim(job, actor, token):
        if job["agent_id"] != actor or not secrets.compare_digest(job["claim_hash"] or "", digest(token)):
            raise LabError("This claim belongs to a different worker or attempt.", 403)

    def heartbeat(self, identifier, actor, token):
        with self.tx() as db:
            job = self.row(db, "jobs", identifier)
            self.check_claim(job, actor, token)
            db.execute("UPDATE jobs SET heartbeat_at=? WHERE id=?", (now(), identifier))
            db.execute("UPDATE agents SET last_seen=? WHERE id=?", (now(), actor))
            return {"status": job["status"], "paused": self.budget(db)["paused"]}

    def complete(self, identifier, p, actor):
        claim = text(p.get("claim_token"), "Claim token", 200)
        status = p.get("status", "completed")
        if status not in {"completed", "failed", "cancelled"}:
            raise LabError("Invalid completion status.")
        actual = p.get("actual_cost_micro")
        if actual is not None:
            money(actual, "Reported cost", limit=10_000 * MICRO)
        if status == "completed" and actual is None:
            raise LabError("Unknown spend must be failed with an outstanding hold.")
        receipt_payload = {k: v for k, v in p.items() if k != "claim_token"}
        fingerprint = digest(json.dumps(receipt_payload, sort_keys=True, separators=(",", ":")))
        with self.tx() as db:
            job = self.row(db, "jobs", identifier)
            self.check_claim(job, actor, claim)
            if job["completion_hash"]:
                if job["completion_hash"] != fingerprint:
                    raise LabError("Conflicting duplicate completion.", 409)
                return json.loads(job["completion_json"])
            if job["status"] not in {"running", "cancel_requested"}:
                raise LabError("This job is not running.", 409)
            artifact_id = None
            if status == "completed":
                a = p.get("artifact")
                if not isinstance(a, dict):
                    raise LabError("A completed job needs an artifact.")
                title = text(a.get("title"), "Artifact title", 300)
                body = text(a.get("body"), "Artifact body", 100_000)
                sources = a.get("sources", [])
                if not isinstance(sources, list) or len(sources) > 50 or any(not isinstance(s, str) or len(s) > 2000 for s in sources):
                    raise LabError("Sources must be a list of at most 50 URL strings.")
                usage = p.get("usage", {})
                if not isinstance(usage, dict) or len(json.dumps(usage)) > 20_000:
                    raise LabError("Invalid usage receipt.")
                provider = text(p.get("provider", "unknown"), "Provider", 100)
                model = text(p.get("model", "unknown"), "Model", 200)
                demo = p.get("is_demo", False)
                if type(demo) is not bool:
                    raise LabError("is_demo must be a boolean.")
                artifact_id = uid("artifact")
                db.execute("""INSERT INTO artifacts(id,job_id,agent_id,title,body,sources_json,usage_json,provider,model,is_demo,created_at)
                              VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                           (artifact_id, identifier, actor, title, body, json.dumps(sources), json.dumps(usage),
                            provider, model, int(demo), now()))
            db.execute("UPDATE jobs SET receipt_json=? WHERE id=?", (json.dumps(receipt_payload), identifier))
            result = {"ok": True, "artifact_id": artifact_id, "unsettled": actual is None}
            db.execute("""UPDATE jobs SET status=?,actual_cost_micro=?,settled_month=?,finished_at=?,
                          completion_hash=?,completion_json=? WHERE id=?""",
                       (status, actual, month() if actual is not None else None, now(), fingerprint, json.dumps(result), identifier))
            note = "Spend unknown; reservation retained." if actual is None else f"Recorded USD {actual / MICRO:.4f}."
            self.event(db, "completed" if status == "completed" else "failed", actor, f"{job['title']}: {status}. {note}")
            if actual is not None and actual > job["max_cost_micro"]:
                db.execute("UPDATE settings SET value='true' WHERE key='paused'")
                self.event(db, "overrun", actor, "Reported cost exceeded the job limit. Claims paused for owner review.")
        return result

    def cancel(self, identifier):
        with self.tx() as db:
            job = self.row(db, "jobs", identifier)
            if job["status"] == "queued":
                db.execute("UPDATE jobs SET status='cancelled',actual_cost_micro=0,settled_month=?,finished_at=? WHERE id=?",
                           (month(), now(), identifier))
            elif job["status"] == "running":
                db.execute("UPDATE jobs SET status='cancel_requested' WHERE id=?", (identifier,))
            elif job["status"] not in {"cancel_requested", "cancelled"}:
                raise LabError("This job has already finished.", 409)
            self.event(db, "cancel", "owner", f"Cancellation requested for {job['title']}. Active spend holds remain until settlement.")
        return {"ok": True}

    def settle(self, identifier, p):
        actual = money(p.get("actual_cost_micro"), "Actual cost", 10_000 * MICRO)
        notes = text(p.get("notes"), "Settlement explanation", 3000)
        with self.tx() as db:
            job = self.row(db, "jobs", identifier)
            if job["status"] not in {"failed", "cancelled"} or job["actual_cost_micro"] is not None:
                raise LabError("Only finished jobs with uncertain spend can be settled manually.", 409)
            db.execute("UPDATE jobs SET actual_cost_micro=?,settled_month=? WHERE id=?", (actual, month(), identifier))
            self.event(db, "settled", "owner", f"{identifier}: USD {actual / MICRO:.4f}. {notes}")
            if actual > job["max_cost_micro"]:
                db.execute("UPDATE settings SET value='true' WHERE key='paused'")
        return {"ok": True}

    def recover(self, identifier, p):
        notes = text(p.get("notes"), "Recovery explanation", 3000)
        with self.tx() as db:
            job = self.row(db, "jobs", identifier)
            if job["status"] not in {"running", "cancel_requested"}:
                raise LabError("Only an interrupted active job can be recovered.", 409)
            # Owner must stop the original process first. This is a terminal
            # transition, never an automatic lease expiry or duplicate retry.
            db.execute("UPDATE jobs SET status='failed',finished_at=? WHERE id=?", (now(),identifier))
            self.event(db,"recovery","owner",f"{identifier}: owner confirmed worker stopped. Spend remains unknown. {notes}")
        return {"ok":True,"unsettled":True}

    def review(self, identifier, p, reviewer):
        verdict = p.get("verdict")
        if verdict not in {"accepted", "changes_requested"}:
            raise LabError("Invalid review verdict.")
        notes = text(p.get("notes"), "Review evidence", 8000)
        with self.tx() as db:
            artifact = self.row(db, "artifacts", identifier)
            self.row(db, "agents", reviewer)
            if artifact["agent_id"] == reviewer:
                raise LabError("The author cannot review their own artifact.", 409)
            if artifact["review_status"] != "pending":
                raise LabError("This artifact has already been reviewed.", 409)
            db.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?)", (uid("review"), identifier, reviewer, verdict, notes, now()))
            db.execute("UPDATE artifacts SET review_status=? WHERE id=?", (verdict, identifier))
            self.event(db, "review", reviewer, f"{artifact['title']}: {verdict}.")
        return {"ok": True}

    def agent_settings(self, identifier, p):
        enabled = p.get("enabled")
        if type(enabled) is not bool:
            raise LabError("enabled must be a boolean.")
        with self.tx() as db:
            self.row(db, "agents", identifier)
            if not enabled and db.execute("SELECT 1 FROM jobs WHERE agent_id=? AND status IN ('running','cancel_requested')", (identifier,)).fetchone():
                raise LabError("Cancel and settle active jobs before disabling their worker.", 409)
            db.execute("UPDATE agents SET enabled=? WHERE id=?", (int(enabled), identifier))
            self.event(db, "worker", "owner", f"{identifier}: {'enabled' if enabled else 'disabled'}.")
        return {"ok": True}
