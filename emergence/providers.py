"""Synthetic demo and official Codex subscription inference; no API-key provider."""
import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from urllib.request import HTTPRedirectHandler

def usd_micro(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValueError("Expected a nonnegative finite USD amount.")
        return int((amount * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
    except InvalidOperation:
        raise ValueError("Invalid USD amount.") from None

class InferenceError(RuntimeError):
    def __init__(self, message, cost=None, usage=None):
        self.cost, self.usage = cost, usage or {}
        super().__init__(message)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

@dataclass
class Result:
    text: str
    cost: int
    usage: dict
    provider: str
    model: str
    is_demo: bool = False

class Demo:
    name, model = "demo", "fixed-response-v1"
    def preflight(self, prompt, cap):
        return 0
    def generate(self, prompt, cap):
        if '"task_type": "deliberation"' in prompt:
            answer = json.dumps({"choice":"abstain","rationale":"Synthetic rehearsal ballot: require matched-cost baselines and held-out evaluation before drawing conclusions."})
        elif "PATCH_SELECTION" in prompt:
            data = json.loads(prompt.split("\n")[-1])
            answer = json.dumps({"patch_id":data.get("demo_reference", "A"),"reason":"Synthetic fixture selects the supplied reference alias."})
        else:
            answer = ("SYNTHETIC WORKFLOW REHEARSAL\n\nQuestion: Does shared memory improve agent coordination?\n\n"
                      "Protocol: compare one iterative agent, independent attempts, a reviewer, and shared memory. "
                      "Hold the model and total resource budget fixed. Measure task correctness, latency, and actual usage.\n\n"
                      "Falsifier: no reliable gain over the strongest matched-budget baseline on fresh tasks.\n\n"
                      "Result: no live inference or scientific experiment was performed by this job. This fixed artifact "
                      "only tests the queue, accounting, and review workflow.\n\n"
                      "Next: run the smoke suite, then design private held-out tasks and independent replications.")
        return Result(answer, 0, {"synthetic":True,"provider_calls":0,"latency_ms":0}, self.name, self.model, True)

class CodexSubscription:
    """Delegate auth to official Codex CLI; never read/copy OAuth credentials."""
    name, model = "codex_subscription", "codex-default"
    def __init__(self):
        import shutil
        import subprocess
        self.binary = shutil.which("codex")
        if not self.binary:
            raise ValueError("Install the official Codex CLI and sign in with ChatGPT first.")
        self.env = {k:v for k,v in os.environ.items() if k not in {
            "OPENAI_API_KEY","CODEX_API_KEY","INFERENCE_API_KEY","OPENAI_BASE_URL",
            "OPENAI_ORGANIZATION","OPENAI_PROJECT","CODEX_ACCESS_TOKEN"}}
        status = subprocess.run([self.binary,"login","status"],env=self.env,capture_output=True,text=True,timeout=15)
        if status.returncode or "Logged in using ChatGPT" not in status.stdout+status.stderr:
            raise ValueError("Subscription worker requires Codex login with ChatGPT. API-key login is not accepted.")
        help_result = subprocess.run([self.binary,"exec","--help"],env=self.env,capture_output=True,text=True,timeout=15)
        if "--ignore-user-config" not in help_result.stdout:
            raise ValueError("Update Codex CLI: this adapter requires --ignore-user-config support.")
        self.timeout = int(os.environ.get("EMERGENCE_CODEX_TIMEOUT_SECONDS","180"))
        if not 15<=self.timeout<=600:
            raise ValueError("EMERGENCE_CODEX_TIMEOUT_SECONDS must be 15..600.")

    def preflight(self,prompt,cap):
        if len(prompt.encode())>100_000:
            raise InferenceError("Prompt exceeds 100 KB; no subscription call sent.",0)
        return 0

    def generate(self,prompt,cap,*,schema=None,web_search=False,model=None):
        import subprocess
        import tempfile
        from pathlib import Path
        self.preflight(prompt,cap)
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="emergence-codex-") as directory:
            output = Path(directory)/"answer.txt"
            command = [self.binary,"exec","--ignore-user-config","--ephemeral","--skip-git-repo-check",
                       "--sandbox","read-only","--json","--color","never","--cd",directory,
                       "--output-last-message",str(output),
                       "-c",'forced_login_method="chatgpt"',"-c",'model_provider="openai"',
                       "-c",'approval_policy="never"',"-c",'web_search="'+("live" if web_search else "disabled")+'"',
                       "-c","project_doc_max_bytes=0","-c","mcp_servers={}"]
            for feature in ("shell_tool","apps","plugins","hooks","multi_agent","computer_use",
                            "browser_use","image_generation","in_app_browser","workspace_dependencies"):
                command += ["-c","features."+feature+"=false"]
            command += ["-c","features.skip_host_skill_discovery=true","-"]
            if schema is not None:
                schema_file=Path(directory)/"response-schema.json"
                schema_file.write_text(json.dumps(schema))
                command[-1:-1]=["--output-schema",str(schema_file)]
            if model:
                command[-1:-1]=["--model",model]
            with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                try:
                    process = subprocess.run(command,input=prompt.encode(),stdout=stdout,stderr=stderr,
                                             env=self.env,timeout=self.timeout,check=False)
                except subprocess.TimeoutExpired:
                    raise InferenceError("Codex timed out. Subscription usage may have occurred; no automatic retry.",0,{"billing":"chatgpt_subscription","usage_unknown":True}) from None
                stdout.seek(0)
                raw = stdout.read(2_000_001)
            receipt = {"billing":"chatgpt_subscription","api_spend_micro":0,
                       "latency_ms":round((time.monotonic()-started)*1000),"configured_model":model or self.model,
                       "quota_note":"Consumes the signed-in account's subscription allowance. No dollar conversion."}
            completed = False
            receipt["tool_events"]=[]
            if len(raw)<=2_000_000:
                for line in raw.splitlines():
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if event.get("type")=="item.completed":
                        item=event.get("item",{})
                        if isinstance(item,dict) and item.get("type")=="web_search" and len(receipt["tool_events"])<20:
                            receipt["tool_events"].append(item)
                    if event.get("type")=="turn.completed":
                        completed = True
                        usage = event.get("usage",{})
                        if isinstance(usage,dict):
                            totals=receipt.setdefault("tokens",{})
                            for key,value in usage.items():
                                if type(value) is int and value>=0:
                                    totals[key]=totals.get(key,0)+value
            if process.returncode or not completed or not output.exists():
                raise InferenceError("Codex did not finish successfully. Check login, account limits, and CLI version; no API fallback.",0,{**receipt,"usage_unknown":not completed})
            content = output.read_text()
            if not content.strip() or len(content)>100_000:
                raise InferenceError("Codex returned empty or oversized text.",0,receipt)
            return Result(content,0,receipt,self.name,model or self.model)

def provider(name):
    if name=="demo":
        return Demo()
    if name=="codex":
        return CodexSubscription()
    raise ValueError("Use demo or codex. API-key inference is disabled in this MVP.")
