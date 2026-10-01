import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from emergence.providers import CodexSubscription, InferenceError, Demo, usd_micro, provider
from emergence.experiment import TASKS, grade
from emergence.worker import perform

class SubscriptionTests(unittest.TestCase):
    def fake_run(self, command, **kwargs):
        if command[1:]==["login","status"]:
            return subprocess.CompletedProcess(command,0,"Logged in using ChatGPT","")
        if "--help" in command:
            return subprocess.CompletedProcess(command,0,"--ignore-user-config","")
        self.assertIn('forced_login_method="chatgpt"',command)
        self.assertIn("--ignore-user-config",command)
        self.assertIn("--sandbox",command)
        self.assertIn("features.shell_tool=false",command)
        self.assertNotIn("OPENAI_API_KEY",kwargs["env"])
        self.assertNotIn("CODEX_API_KEY",kwargs["env"])
        Path(command[command.index("--output-last-message")+1]).write_text("A verified fixture response.")
        kwargs["stdout"].write(json.dumps({"type":"turn.completed","usage":{"input_tokens":20,"output_tokens":5}}).encode()+b"\n")
        return subprocess.CompletedProcess(command,0)
    @patch("shutil.which",return_value="/mock/codex")
    def test_subscription_command_and_receipt(self,_):
        with patch.dict(os.environ,{"OPENAI_API_KEY":"not-a-real-key","CODEX_API_KEY":"not-a-real-key"}), patch("subprocess.run",side_effect=self.fake_run):
            result=CodexSubscription().generate("Research fixture",0)
        self.assertEqual(result.cost,0)
        self.assertEqual(result.usage["billing"],"chatgpt_subscription")
        self.assertEqual(result.usage["tokens"]["output_tokens"],5)
    @patch("shutil.which",return_value="/mock/codex")
    def test_api_login_rejected(self,_):
        with patch("subprocess.run",return_value=subprocess.CompletedProcess([],0,"Logged in using an API key","")):
            with self.assertRaises(ValueError):CodexSubscription()
    def test_api_provider_is_disabled(self):
        with self.assertRaises(ValueError):provider("compatible")
    @patch("shutil.which",return_value="/mock/codex")
    def test_timeout_reports_subscription_usage_unknown(self,_):
        with patch("subprocess.run",side_effect=self.fake_run):engine=CodexSubscription()
        with patch("subprocess.run",side_effect=subprocess.TimeoutExpired([],180)):
            with self.assertRaises(InferenceError) as err:engine.generate("Question",0)
        self.assertEqual(err.exception.cost,0)
        self.assertTrue(err.exception.usage["usage_unknown"])

class GraderTests(unittest.TestCase):
    def test_reference_and_bad_repairs(self):
        for task in TASKS:
            self.assertEqual(grade(task,"correct"),1)
            self.assertEqual(grade(task,"untrusted code"),0)
            for bad in task["candidates"].keys()-{"correct"}:
                self.assertLess(grade(task,bad),1)
    def test_microdollar_rounding(self):
        self.assertEqual(usd_micro("0.0000001"),1)
        for value in ["NaN","Infinity","-1"]:
            with self.assertRaises(ValueError):usd_micro(value)
    def test_demo_deliberation(self):
        job={"kind":"deliberation","role":"critic","prompt":"Review","proposal":{},"proposal_id":"p",
             "max_cost_micro":0,"claim_token":"claim","title":"Ballot"}
        state={key:[] for key in ["artifacts","comments","ballots","atlas"]}
        calls=[]
        receipt=perform(job,state,Demo(),lambda path,body:calls.append((path,body)))
        self.assertEqual(receipt["status"],"completed")
        self.assertEqual(calls[0][1]["choice"],"abstain")
        self.assertTrue(receipt["is_demo"])

if __name__=="__main__":
    unittest.main()
