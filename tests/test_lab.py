import concurrent.futures
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from emergence.db import Lab, LabError, MICRO
from emergence.demo import rehearse
from emergence.server import Server

class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lab = Lab(self.temp.name)
        self.pid = "proposal_first"
        self.lab.decide(self.pid,{"decision":"approved"})
    def job(self, cap=1_000_000, role="researcher"):
        return self.lab.enqueue({"proposal_id":self.pid,"title":"Test job","prompt":"Test instructions","role":role,"max_cost_micro":cap})["id"]
    def receipt(self, job, cost=100, status="completed"):
        return {"claim_token":job["claim_token"],"status":status,"actual_cost_micro":cost,
                "provider":"test","model":"fixture","usage":{"tokens":1},
                "artifact":{"title":"Measured artifact","body":"A test-only result.","sources":[]}}
    def test_fresh_seed_and_add_source(self):
        self.assertEqual(len(self.lab.state()["atlas"]),8)
        self.lab.add_atlas({"area":"Test","title":"Source","url":"https://example.com","summary":"Claim","limitations":"Unverified"})
        self.assertEqual(len(self.lab.state()["atlas"]),9)
    def test_atomic_budget_reservations(self):
        self.lab.settings({"monthly_limit_micro":MICRO})
        def enqueue(_):
            try:
                return self.job(800_000)
            except LabError:
                return None
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            ids = list(pool.map(enqueue,range(4)))
        self.assertEqual(sum(x is not None for x in ids),1)
        self.assertEqual(self.lab.state()["budget"]["reserved_micro"],800_000)
    def test_atomic_single_claim(self):
        self.job()
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            jobs=list(pool.map(lambda _:self.lab.claim("researcher")["job"],range(4)))
        self.assertEqual(sum(j is not None for j in jobs),1)
    def test_completion_idempotent_and_review_distinct(self):
        self.job()
        job=self.lab.claim("researcher")["job"]
        receipt=self.receipt(job)
        first=self.lab.complete(job["id"],receipt,"researcher")
        self.assertEqual(first,self.lab.complete(job["id"],receipt,"researcher"))
        with self.assertRaises(LabError):
            self.lab.complete(job["id"],{**receipt,"actual_cost_micro":200},"researcher")
        with self.assertRaises(LabError):
            self.lab.review(first["artifact_id"],{"verdict":"accepted","notes":"Self review"},"researcher")
        self.lab.review(first["artifact_id"],{"verdict":"accepted","notes":"Checked fixture."},"critic")
        self.assertEqual(self.lab.state()["budget"]["spent_micro"],100)
        self.assertEqual(len(self.lab.state()["artifacts"]),1)
    def test_cancel_queued_releases_running_retains(self):
        jid=self.job()
        self.lab.cancel(jid)
        self.assertEqual(self.lab.state()["budget"]["reserved_micro"],0)
        jid=self.job()
        self.lab.claim("researcher")
        self.lab.cancel(jid)
        self.assertEqual(self.lab.state()["budget"]["reserved_micro"],MICRO)
        with self.assertRaises(LabError):
            self.lab.settle(jid,{"actual_cost_micro":0,"notes":"Still running"})
        self.lab.recover(jid,{"notes":"Original process stopped."})
        self.lab.settle(jid,{"actual_cost_micro":120,"notes":"Checked provider receipt."})
        self.assertEqual(self.lab.state()["budget"]["reserved_micro"],0)
    def test_unknown_cost_and_failed_receipt(self):
        jid=self.job()
        job=self.lab.claim("researcher")["job"]
        self.lab.complete(jid,self.receipt(job,None,"failed"),"researcher")
        state=self.lab.state()
        self.assertEqual(state["budget"]["reserved_micro"],MICRO)
        self.assertEqual(json.loads(state["jobs"][0]["receipt_json"])["usage"],{"tokens":1})
        self.lab.settle(jid,{"actual_cost_micro":250,"notes":"Provider confirmed cost."})
        self.assertEqual(self.lab.state()["budget"]["spent_micro"],250)
    def test_pending_receipt_after_recovery_preserves_manual_settlement(self):
        jid=self.job()
        job=self.lab.claim("researcher")["job"]
        receipt=self.receipt(job,100)
        self.lab.recover(jid,{"notes":"Worker stopped after saving its receipt."})
        self.lab.settle(jid,{"actual_cost_micro":125,"notes":"Verified separately."})
        result=self.lab.complete(jid,receipt,"researcher")
        self.assertEqual(result,self.lab.complete(jid,receipt,"researcher"))
        self.assertEqual(self.lab.state()["budget"]["spent_micro"],125)
        self.assertEqual(len(self.lab.state()["artifacts"]),1)
    def test_month_rollover_preserves_holds(self):
        self.job()
        with patch("emergence.db.month",return_value="2099-01"):
            self.assertEqual(self.lab.state()["budget"]["reserved_micro"],MICRO)
            self.assertEqual(self.lab.state()["budget"]["spent_micro"],0)
    def test_overrun_cannot_resume_negative_budget(self):
        self.lab.settings({"monthly_limit_micro":2*MICRO})
        self.job(); self.job()
        job=self.lab.claim("researcher")["job"]
        self.lab.complete(job["id"],self.receipt(job,1_500_000,"failed"),"researcher")
        self.assertTrue(self.lab.state()["budget"]["paused"])
        with self.assertRaises(LabError):
            self.lab.settings({"paused":False})
        self.assertIsNone(self.lab.claim("researcher")["job"])
    def test_foreign_completion_and_invalid_money(self):
        self.job()
        job=self.lab.claim("researcher")["job"]
        with self.assertRaises(LabError):
            self.lab.complete(job["id"],self.receipt(job),"scout")
        with self.assertRaises(LabError):
            self.job(True)
    def test_deliberation_before_approval(self):
        pid=self.lab.proposal({"title":"Question","area":"Agents","question":"Q?","hypothesis":"H","baseline":"B","evaluation":"E","deliverables":"D","budget_micro":0})["id"]
        jid=self.lab.enqueue({"proposal_id":pid,"title":"Deliberate","prompt":"Evaluate","role":"critic","kind":"deliberation","max_cost_micro":0})["id"]
        job=self.lab.claim("critic",0)["job"]
        self.assertEqual(job["id"],jid)
        self.lab.vote(pid,{"choice":"oppose","rationale":"Need a stronger baseline."},"critic")
        self.assertEqual(self.lab.state()["ballots"][0]["choice"],"oppose")
    def test_demo_is_explicit_and_zero_cost(self):
        receipt=rehearse(self.lab)
        state=self.lab.state()
        self.assertTrue(receipt["is_demo"])
        self.assertEqual(state["budget"]["spent_micro"],0)
        self.assertEqual(state["artifacts"][0]["is_demo"],1)
        self.assertEqual(state["artifacts"][0]["review_status"],"accepted")

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.lab=Lab(self.temp.name)
        self.server=Server(("127.0.0.1",0),self.lab)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url="http://127.0.0.1:"+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def send(self,path,payload=None,headers=None):
        h={"Content-Type":"application/json",**(headers or {})}
        req=Request(self.url+path,data=json.dumps(payload).encode() if payload is not None else None,headers=h)
        try:
            return urlopen(req,timeout=5)
        except HTTPError as error:
            error.close()
            raise
    def test_owner_csrf_and_worker_route(self):
        with self.assertRaises(HTTPError) as err:
            self.send("/api/settings",{"paused":True})
        self.assertEqual(err.exception.code,403)
        with self.assertRaises(HTTPError):
            self.send("/api/settings",{"paused":True},{"X-Lab-Request":"1","Origin":"https://evil.example"})
        token=self.lab.issue_token("critic")
        with self.assertRaises(HTTPError):
            self.send("/api/settings",{"paused":True},{"X-Lab-Request":"1","Authorization":"Bearer "+token})
        with self.send("/api/worker/claim",{},{"Authorization":"Bearer "+token}) as response:
            self.assertIsNone(json.load(response)["job"])
    def test_state_contains_no_credentials_and_csp(self):
        token=self.lab.issue_token("scout")
        with self.send("/api/state") as response:
            body=response.read().decode()
            self.assertNotIn(token,body)
            self.assertNotIn("token_hash",body)
            self.assertIn("frame-ancestors 'none'",response.headers["Content-Security-Policy"])
    def test_host_and_body_limits(self):
        with self.assertRaises(HTTPError):
            self.send("/api/state",headers={"Host":"evil.example"})
        with self.assertRaises(HTTPError) as err:
            self.send("/api/settings",{"padding":"x"*200001},{"X-Lab-Request":"1"})
        self.assertEqual(err.exception.code,413)
    def test_mission_routes_and_export_include_new_records(self):
        body={"provider":"demo","call_limit":8,"cycle_limit":1,"objective":"Test evidence retrieval."}
        with self.assertRaises(HTTPError):self.send("/api/missions",body)
        with self.send("/api/missions",body,{"X-Lab-Request":"1"}) as response:
            mid=json.load(response)["id"]
        with self.send("/api/missions?id="+mid) as response:
            snapshot=json.load(response)
            self.assertEqual(snapshot["selected"],mid)
            self.assertEqual(snapshot["missions"][0]["status"],"ready")
        with self.send("/api/export") as response:
            exported=json.load(response)
            self.assertEqual(exported["format_version"],2)
            self.assertEqual(exported["autonomy"]["missions"][0]["id"],mid)
            self.assertEqual(len(exported["autonomy"]["mission_messages"]),1)

    def test_reports_allow_owner_feedback_and_block_withdrawn_downloads(self):
        from emergence.autonomy import run_mission
        missions=self.server.mission_manager.missions
        mid=missions.create({'provider':'demo','call_limit':8,'cycle_limit':1})['id']
        missions.control(mid,'start')
        receipt={'status':'passed','data':{'verified':True},'stdout':'{"verified":true}',
                 'stderr':'','code_sha256':'fixture'}
        with patch('emergence.autonomy.run_python',return_value=receipt), patch('emergence.autonomy.capability',return_value={'available':True}):
            state=run_mission(self.lab,mid)
        report=state['reports'][0];path='/api/reports/'+report['id']
        with self.send(path+'/download') as response:
            self.assertIn('attachment',response.headers['Content-Disposition'])
            self.assertIn('SYNTHETIC REHEARSAL',response.read().decode())
        feedback={'value':'useful','reason':'This documents the intended workflow clearly.'}
        token=self.lab.issue_token('critic')
        with self.assertRaises(HTTPError) as err:
            self.send(path+'/feedback',feedback,{'X-Lab-Request':'1','Authorization':'Bearer '+token})
        self.assertEqual(err.exception.code,403)
        with self.send(path+'/feedback',feedback,{'X-Lab-Request':'1'}) as response:
            self.assertTrue(json.load(response)['ok'])
        with self.lab.tx() as db:
            db.execute("UPDATE mission_claims SET status='retracted' WHERE id=?",(report['claim_id'],))
        with self.assertRaises(HTTPError) as err:self.send(path+'/download')
        self.assertEqual(err.exception.code,409)

if __name__=="__main__":
    unittest.main()
