import argparse
from .db import LabError

def main():
    parser = argparse.ArgumentParser(description="Emergence Lab — a local collective AI research lab.")
    parser.add_argument("--data-dir", default=".emergence", help="Private local state (default: .emergence)")
    sub = parser.add_subparsers(dest="command", required=True)
    server = sub.add_parser("serve", help="Start the local dashboard")
    server.add_argument("--port", type=int, default=7331)
    worker = sub.add_parser("worker", help="Run a contributor-owned worker")
    worker.add_argument("--agent", choices=["scout", "researcher", "critic", "coordinator"], default="researcher")
    worker.add_argument("--provider", choices=["demo", "codex"], default="demo")
    worker.add_argument("--url", default="http://127.0.0.1:7331")
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--max-jobs", type=int, default=1)
    worker.add_argument("--max-job-usd", default="1")
    worker.add_argument("--poll-seconds", type=int, default=5)
    experiment = sub.add_parser("experiment", help="Compare workflows on a small repair-selection smoke suite")
    experiment.add_argument("--provider", choices=["demo", "codex"], default="demo")
    experiment.add_argument("--seed", type=int, default=17)
    experiment.add_argument("--out", default=".emergence/experiments/latest.json")
    experiment.add_argument("--max-cost-usd", default="1")
    sub.add_parser("demo", help="Run the zero-cost workflow rehearsal")
    mission = sub.add_parser("mission",help="Run an autonomous research mission without intermediate approvals")
    mission.add_argument("--objective",default=None)
    mission.add_argument("--provider",choices=["demo","codex"],default="demo")
    mission.add_argument("--calls",type=int,default=12)
    mission.add_argument("--cycles",type=int,default=2)
    mission.add_argument("--minutes",type=int,default=20)
    mission.add_argument("--model",default="")
    args = parser.parse_args()
    if args.command == "serve":
        from .server import serve
        serve(args.data_dir, args.port)
    elif args.command == "worker":
        from .worker import run
        run(args)
    elif args.command == "experiment":
        from .experiment import run
        run(args)
    elif args.command=="mission":
        from .autonomy import Missions,run_mission,DEFAULT_OBJECTIVE
        from .db import Lab
        import json
        lab=Lab(args.data_dir)
        missions=Missions(lab)
        identifier=missions.create({"objective":args.objective or DEFAULT_OBJECTIVE,"provider":args.provider,
                                    "call_limit":args.calls,"cycle_limit":args.cycles,"minutes":args.minutes,
                                    "model":args.model})["id"]
        missions.control(identifier,"start")
        print("Autonomous mission: "+identifier,flush=True)
        result=run_mission(lab,identifier)
        print(json.dumps(next(m for m in result["missions"] if m["id"]==identifier),indent=2))
    else:
        from .db import Lab
        from .demo import rehearse
        import json
        print(json.dumps(rehearse(Lab(args.data_dir)), indent=2))

if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, LabError) as exc:
        raise SystemExit(str(exc)) from None
