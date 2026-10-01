import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from emergence.db import Lab
from emergence.experiment import run
from emergence.providers import Demo, InferenceError, Result

class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.args=SimpleNamespace(data_dir=self.temp.name,provider="demo",max_cost_usd="0",seed=17,out=self.temp.name+"/latest.json")
    def invoke(self):
        with contextlib.redirect_stdout(io.StringIO()):
            run(self.args)
        return Lab(self.temp.name).state()
    def test_demo_uses_grader_and_keeps_immutable_reports(self):
        self.invoke();state=self.invoke()
        self.assertEqual(len(list((Path(self.temp.name)/"experiments").glob("job_*.json"))),2)
        self.assertEqual(len(state["artifacts"]),2)
    def test_first_call_failure_settles(self):
        engine=Demo()
        with patch.object(engine,"generate",side_effect=InferenceError("Preflight failed",0)),patch("emergence.experiment.provider",return_value=engine):
            state=self.invoke()
        self.assertEqual(state["jobs"][0]["status"],"failed")
        self.assertEqual(state["budget"]["reserved_micro"],0)
        report=json.loads(Path(self.args.out).read_text())
        self.assertTrue(all(x["mean_score"] is None for x in report["summary"].values()))
    def test_malformed_candidate_does_not_crash(self):
        engine=Demo()
        with patch.object(engine,"generate",return_value=Result('{"patch_id":[]}',0,{},"demo","fixture",True)),patch("emergence.experiment.provider",return_value=engine):
            state=self.invoke()
        self.assertEqual(state["jobs"][0]["status"],"completed")
        report=json.loads(Path(self.args.out).read_text())
        self.assertTrue(all(x["mean_score"]==0 for x in report["summary"].values()))
    def test_report_write_failure_settles(self):
        self.args.out=self.temp.name
        state=self.invoke()
        self.assertEqual(state["jobs"][0]["status"],"failed")
        self.assertEqual(state["jobs"][0]["actual_cost_micro"],0)
