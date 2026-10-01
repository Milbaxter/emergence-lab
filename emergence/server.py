"""Loopback-only HTTP dashboard and worker protocol."""
from __future__ import annotations
import json
import mimetypes
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from .db import Lab, LabError, text

STATIC = Path(__file__).parent / "static"
MAX_BODY = 200_000

class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, lab):
        self.lab = lab
        self.demo_lock = threading.Lock()
        from .autonomy import MissionManager
        self.mission_manager = MissionManager(lab)
        super().__init__(address, Handler)

class Handler(BaseHTTPRequestHandler):
    server_version = "EmergenceLab/0.3"
    def log_message(self, fmt, *args):
        # No request bodies, credentials, prompts or query strings in logs.
        pass

    @property
    def lab(self):
        return self.server.lab

    def check_host(self):
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host") not in allowed:
            raise LabError("This service only accepts its loopback hostname.", 403)
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + h for h in allowed}:
            raise LabError("Cross-origin requests are not allowed.", 403)
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise LabError("Cross-site requests are not allowed.", 403)

    def send(self, payload, status=200, content_type="application/json; charset=utf-8", download=None):
        body = json.dumps(payload, ensure_ascii=False).encode() if isinstance(payload, (dict, list)) else payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if download:
            self.send_header("Content-Disposition", 'attachment; filename="' + download + '"')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def error(self, exc):
        if isinstance(exc, LabError):
            self.send({"error": str(exc)}, exc.status)
        else:
            self.send({"error": "Internal error. Check the local server terminal."}, 500)
            import traceback
            traceback.print_exc()

    def body(self):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise LabError("Send application/json.", 415)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise LabError("Invalid content length.") from None
        if not 0 < length <= MAX_BODY:
            raise LabError("Request body is empty or too large.", 413)
        try:
            data = json.loads(self.rfile.read(length), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeDecodeError):
            raise LabError("Invalid JSON.") from None
        if not isinstance(data, dict):
            raise LabError("Expected a JSON object.")
        return data

    def worker(self):
        value = self.headers.get("Authorization", "")
        if not value.startswith("Bearer "):
            raise LabError("A worker bearer credential is required.", 401)
        return self.lab.authenticate(value[7:])["id"]

    def owner(self):
        if self.headers.get("Authorization"):
            raise LabError("Worker credentials cannot access owner actions.", 403)
        if self.headers.get("X-Lab-Request") != "1":
            raise LabError("A same-origin owner request is required.", 403)

    def do_GET(self):
        try:
            self.check_host()
            path = urlsplit(self.path).path
            if path == "/api/state":
                self.send(self.lab.state())
            elif path == "/api/missions":
                query=parse_qs(urlsplit(self.path).query)
                self.send(self.server.mission_manager.missions.state(query.get("id",[None])[0]))
            elif path == "/api/health":
                self.send({"ok": True, "version": "0.3.0"})
            elif path == "/api/export":
                self.send({"format_version":2,"lab":self.lab.state(),"autonomy":self.server.mission_manager.missions.export()}, download="emergence-lab-export.json")
            elif re.fullmatch(r'/api/reports/[a-zA-Z0-9_]+/download',path):
                from .quality import download
                with self.lab.tx() as db:
                    body=download(db,path.split('/')[3])
                self.send(body,content_type='text/html; charset=utf-8',download=path.split('/')[3]+'.html')
            elif re.fullmatch(r"/api/artifacts/[a-zA-Z0-9_]+/download", path):
                identifier = path.split("/")[3]
                with self.lab.tx() as db:
                    artifact = self.lab.row(db, "artifacts", identifier)
                body = artifact["body"]
                if artifact["is_demo"]:
                    body = "SYNTHETIC DEMO — fixed responses; not evidence of AI capability.\n\n" + body
                self.send(body.encode(), content_type="text/plain; charset=utf-8", download=identifier + ".md")
            elif path in {"/", "/index.html", "/app.js", "/missions.js", "/style.css", "/favicon.svg"}:
                file = STATIC / ("index.html" if path == "/" else path[1:])
                if not file.exists():
                    raise LabError("File not found.", 404)
                self.send(file.read_bytes(), content_type=mimetypes.guess_type(str(file))[0] or "application/octet-stream")
            else:
                raise LabError("Not found.", 404)
        except Exception as exc:
            self.error(exc)

    def do_POST(self):
        try:
            self.check_host()
            p = self.body()
            path = urlsplit(self.path).path
            if path.startswith("/api/worker/"):
                actor = self.worker()
                route = path[len("/api/worker/"):]
                if route == "claim":
                    result = self.lab.claim(actor, p.get("max_job_micro", 90_000_000))
                elif re.fullmatch(r"jobs/[a-zA-Z0-9_]+/(heartbeat|complete)", route):
                    _, identifier, action = route.split("/")
                    result = (self.lab.complete(identifier, p, actor) if action == "complete"
                              else self.lab.heartbeat(identifier, actor, text(p.get("claim_token"), "Claim token", 200)))
                elif re.fullmatch(r"proposals/[a-zA-Z0-9_]+/(vote|comment)", route):
                    _, identifier, action = route.split("/")
                    result = self.lab.vote(identifier, p, actor) if action == "vote" else self.lab.comment(identifier, p, actor)
                elif re.fullmatch(r"artifacts/[a-zA-Z0-9_]+/review", route):
                    result = self.lab.review(route.split("/")[1], p, actor)
                else:
                    raise LabError("Worker action not found.", 404)
            else:
                self.owner()
                if path == "/api/missions":
                    result=self.server.mission_manager.missions.create(p)
                elif re.fullmatch(r'/api/reports/[a-zA-Z0-9_]+/feedback',path):
                    from .quality import feedback
                    with self.lab.tx() as db:
                        result=feedback(db,path.split('/')[3],p.get('value'),p.get('reason'))
                elif re.fullmatch(r'/api/missions/[a-zA-Z0-9_]+/refine',path):
                    result=self.server.mission_manager.missions.refine(path.split('/')[3])
                    self.server.mission_manager.start(result['id'])
                elif re.fullmatch(r"/api/missions/[a-zA-Z0-9_]+/(start|pause|stop)",path):
                    identifier,action=path.split("/")[3:5]
                    result=(self.server.mission_manager.start(identifier) if action=="start"
                            else self.server.mission_manager.missions.control(identifier,action))
                elif path == "/api/proposals":
                    result = self.lab.proposal(p)
                elif path == "/api/atlas":
                    result = self.lab.add_atlas(p)
                elif path == "/api/jobs":
                    result = self.lab.enqueue(p)
                elif path == "/api/settings":
                    result = self.lab.settings(p)
                elif path == "/api/demo":
                    from .demo import rehearse
                    with self.server.demo_lock:
                        result = rehearse(self.lab)
                elif re.fullmatch(r"/api/proposals/[a-zA-Z0-9_]+/(decision|comment|vote)", path):
                    identifier, action = path.split("/")[3:5]
                    if action == "decision":
                        result = self.lab.decide(identifier, p)
                    elif action == "comment":
                        result = self.lab.comment(identifier, p)
                    else:
                        result = self.lab.vote(identifier, p, text(p.get("agent_id"), "Agent", 80))
                elif re.fullmatch(r"/api/jobs/[a-zA-Z0-9_]+/(cancel|settle|recover)", path):
                    identifier, action = path.split("/")[3:5]
                    result = self.lab.cancel(identifier) if action == "cancel" else getattr(self.lab,action)(identifier, p)
                elif re.fullmatch(r"/api/artifacts/[a-zA-Z0-9_]+/review", path):
                    result = self.lab.review(path.split("/")[3], p, text(p.get("reviewer"), "Reviewer", 80))
                elif re.fullmatch(r"/api/agents/[a-zA-Z0-9_]+/settings", path):
                    result = self.lab.agent_settings(path.split("/")[3], p)
                else:
                    raise LabError("Action not found.", 404)
            self.send(result, 200)
        except Exception as exc:
            self.error(exc)

    def do_OPTIONS(self):
        self.send({"error": "Cross-origin access is disabled."}, 403)

def serve(directory, port=7331):
    lab = Lab(directory)
    server = Server(("127.0.0.1", port), lab)
    print(f"Emergence Lab: http://127.0.0.1:{server.server_port}", flush=True)
    print("Local-only. Data: " + str(lab.directory), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
