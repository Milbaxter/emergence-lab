"""Explicit synthetic rehearsal, kept separate from scientific results."""
from .db import LabError
from .providers import Demo

def rehearse(lab):
    # Avoid touching existing queued work or impersonating active workers.
    state = lab.state()
    if state["budget"]["paused"]:
        raise LabError("Resume the lab before running a rehearsal.",409)
    if any(j["status"] in {"queued","running","cancel_requested"} for j in state["jobs"]):
        raise LabError("Finish or cancel existing work before the demo rehearsal.",409)
    if not all(a["enabled"] for a in state["agents"]):
        raise LabError("Enable all four roles before the demo rehearsal.",409)
    pid = lab.proposal({
        "title":"Demo: test the collective research workflow","area":"Workflow rehearsal",
        "question":"Can the lab track a proposal, ballots, execution, cost, and a separate review?",
        "hypothesis":"The state machine preserves a complete, inspectable record.",
        "baseline":"No inference; fixed responses and a zero-dollar job.",
        "evaluation":"Verify separate proposal, ballot, job, artifact, and review records.",
        "deliverables":"One explicitly synthetic artifact and review.","budget_micro":0})["id"]
    for agent in state["agents"]:
        lab.vote(pid,{"choice":"support","rationale":"Synthetic ballot: support rehearsing the workflow; this says nothing about AGI."},agent["id"])
    lab.decide(pid,{"decision":"approved"})
    jid = lab.enqueue({"proposal_id":pid,"title":"Demo research protocol","role":"researcher","kind":"research","max_cost_micro":0,"prompt":"Rehearse the research workflow."})["id"]
    job = lab.claim("researcher",0,jid)["job"]
    if not job or job["id"] != jid:
        raise LabError("The demo job could not be claimed. Inspect the queue.",409)
    r = Demo().generate(job["prompt"],0)
    receipt = lab.complete(jid,{"claim_token":job["claim_token"],"status":"completed","actual_cost_micro":0,
                              "provider":r.provider,"model":r.model,"is_demo":True,"usage":r.usage,
                              "artifact":{"title":"Demo: a falsifiable coordination experiment","body":r.text,
                                          "sources":["https://github.com/PrimeIntellect-ai/verifiers"]}},"researcher")
    lab.review(receipt["artifact_id"],{"verdict":"accepted","notes":"Synthetic review: the artifact correctly discloses fixed responses and zero inference. Accepted only as a workflow rehearsal, not as a research result."},"critic")
    lab.decide(pid,{"decision":"closed"})
    return {"ok":True,"proposal_id":pid,"artifact_id":receipt["artifact_id"],"is_demo":True,"cost_micro":0}
