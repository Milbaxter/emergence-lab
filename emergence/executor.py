"""Run generated, stdlib-only Python behind an OS sandbox, never on the bare host."""
import hashlib
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
import tempfile
import time

def _backend():
    if platform.system() == "Darwin" and Path("/usr/bin/sandbox-exec").exists():
        return {"available":True,"backend":"macOS Seatbelt","details":"No network; read access limited to the experiment and Python runtime; writes stay in the experiment."}
    return {"available":False,"backend":"unavailable","details":"This release executes generated Python only on macOS with Seatbelt. Other hosts retain code for inspection and mark execution unavailable."}

@lru_cache(maxsize=1)
def capability():
    backend=_backend()
    if not backend["available"]:
        return backend
    with tempfile.TemporaryDirectory(prefix="emergence-probe-") as scratch:
        sentinel=Path(scratch)/"outside.txt"
        sentinel.write_text("probe")
        code=("import json,math,random,statistics,pathlib,socket,os\n"
              "denied=[]\n"
              "for fn in (lambda: pathlib.Path("+repr(str(sentinel))+ ").read_text(), "
              "lambda: socket.socket().connect(('127.0.0.1',9)), lambda: os.fork()):\n"
              "    try: fn()\n"
              "    except PermissionError: denied.append(True)\n"
              "    except OSError: denied.append(False)\n"
              "    else: denied.append(False)\n"
              "print(json.dumps({'isolated':len(denied)==3 and all(denied)}))\n")
        receipt=run_python(Path(scratch)/"trial",code,timeout=5,_probe=True)
    if receipt["status"]!="passed" or receipt.get("data")!={"isolated":True}:
        return {"available":False,"backend":backend["backend"],"details":"Sandbox capability probe failed; generated code execution disabled. No unsandboxed fallback."}
    return {**backend,"probe":"passed"}

def _interpreter():
    app=Path(sys.base_prefix)/"Resources/Python.app/Contents/MacOS/Python"
    return app.resolve() if app.exists() else Path(sys.executable).resolve()

def _profile(workspace):
    roots = {str(Path(sys.base_prefix).resolve()),str(Path(sys.executable).resolve().parent),
             "/System/Library","/usr/lib","/usr/share","/private/var/db/dyld",
             str(workspace.resolve())}
    reads = " ".join("(subpath "+json.dumps(p)+")" for p in sorted(roots))
    return ('(version 1)(deny default)\n'
            '(allow process-exec (literal '+json.dumps(str(_interpreter()))+'))\n'
            '(allow sysctl-read)\n'
            '(allow signal (target self))\n'
            '(allow file-read-metadata)\n'
            '(allow file-read-data (literal "/"))\n'
            '(allow file-read* '+reads+' (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))\n'
            '(allow file-write* (subpath '+json.dumps(str(workspace.resolve()))+') (literal "/dev/null"))\n')

def _within_quota(directory):
    size=count=0
    for root,dirs,files in os.walk(directory,followlinks=False):
        for name in dirs+files:
            p=Path(root)/name
            mode=p.lstat().st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                return False
            count+=1
            size+=p.lstat().st_size
            if count>128 or size>2_000_000:
                return False
    return True

def _result_json(raw):
    value=json.loads(raw,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    pending=[(value,0)]
    while pending:
        item,depth=pending.pop()
        if depth>32 or (isinstance(item,float) and not math.isfinite(item)):
            raise ValueError("Result exceeds nesting limit or contains nonfinite numbers.")
        if isinstance(item,dict):
            pending.extend((v,depth+1) for v in item.values())
        elif isinstance(item,list):
            pending.extend((v,depth+1) for v in item)
    return value

def run_python(directory, code, *, subject=None, timeout=12, _probe=False):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True,exist_ok=False,mode=0o700)
    if not isinstance(code,str) or not 0 < len(code) <= 60_000:
        raise ValueError("Experiment code must contain 1..60000 characters.")
    script = directory/"experiment.py"
    script.write_text(code)
    if subject is not None:
        (directory/"subject.py").write_text(subject)
    digest = hashlib.sha256(code.encode()).hexdigest()
    backend = _backend() if _probe else capability()
    started = time.monotonic()
    result = {"backend":backend["backend"],"code_sha256":digest,"status":"unavailable",
              "exit_code":None,"stdout":"","stderr":"","data":None,"elapsed_ms":0,
              "limits":{"wall_seconds":timeout,"cpu_seconds":8,"output_file_bytes":64_000,"workspace_bytes":2_000_000,"workspace_files":128,"rss_watchdog_mb":256,"hard_memory_limit":False},
              "note":"Execution is a measurement, not proof that a scientific claim is true."}
    if not backend["available"]:
        result["stderr"] = backend["details"]
    else:
        # The generated code receives no account credentials or inherited environment.
        env = {"PATH":str(Path(sys.executable).parent)+":/usr/bin:/bin",
               "LANG":"en_US.UTF-8","TMPDIR":str(directory),"PYTHONHASHSEED":"0"}
        with tempfile.TemporaryDirectory(prefix="emergence-policy-") as policy_dir, tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            policy=Path(policy_dir)/"sandbox.sb"
            policy.write_text(_profile(directory))
            command=[sys.executable,"-I","-S","-B",str(Path(__file__).with_name("executor_launcher.py")),
                     str(policy),str(_interpreter()),str(script)]
            process = subprocess.Popen(command,cwd=directory,env=env,stdout=stdout,stderr=stderr,
                                       start_new_session=True,stdin=subprocess.DEVNULL,close_fds=True)
            try:
                while process.poll() is None:
                    if time.monotonic()-started>=timeout:
                        result["status"]="timeout"
                        break
                    try:
                        within=_within_quota(directory)
                    except OSError:
                        within=False
                    if not within:
                        result["status"]="output_limit"
                        break
                    # macOS Python has a huge reserved address space: RLIMIT_AS is not a usable
                    # fixed RAM cap. This trusted-parent RSS watchdog is best effort, not a VM.
                    sample=subprocess.run(["/bin/ps","-o","rss=","-p",str(process.pid)],capture_output=True,text=True,timeout=1)
                    if sample.stdout.strip().isdigit() and int(sample.stdout.strip())>256*1024:
                        result["status"]="memory_limit"
                        break
                    time.sleep(0.05)
                else:
                    result["status"] = "passed" if process.returncode==0 else "failed"
                    if not _within_quota(directory):
                        result["status"]="output_limit"
            finally:
                # Fork is denied by policy. Kill only this child, and only while
                # it is still running; an exited group may no longer be ours.
                if process.poll() is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    except PermissionError:
                        result["status"]="unavailable"
                        result["note"]="The OS rejected terminating the sandbox child; execution is unavailable."
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    result["status"]="unavailable"
                    result["note"]="Sandbox process did not exit promptly; no unsandboxed fallback."
            result["exit_code"] = process.returncode
            for field,stream in (("stdout",stdout),("stderr",stderr)):
                stream.seek(0)
                result[field]=stream.read(64_000).decode(errors="replace")
        try:
            result["data"] = _result_json(result["stdout"])
        except (ValueError,RecursionError):
            if result["status"]=="passed":
                result["status"]="invalid_output"
        result["elapsed_ms"] = round((time.monotonic()-started)*1000)
    # Use a separate trusted receipt outside the writable sandbox.
    return result
