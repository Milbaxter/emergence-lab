# Emergence Lab

A local, open-source research team that chooses questions, critiques methods, runs experiments, and updates shared findings within a mission you set.

**You set the direction and allowance. Agents make routine research decisions without approval clicks.** The long-term hypothesis is that interaction can improve collective intelligence. This release makes that hypothesis testable; it does not demonstrate AGI, superintelligence, or spontaneous self-organization.

Pilot: one owner, four roles, ChatGPT subscription inference through the official Codex CLI, local SQLite, and off-chain rules. No API-key provider, external hosting, token issuance, or automatic purchases.

## Start a mission

Python 3.11+; no Python runtime dependencies. **Generated experiment execution currently requires macOS with a working Seatbelt sandbox.** On Linux, the dashboard and inference work, but generated code is retained without execution and findings cannot become peer checked. Windows is not supported.

```sh
git clone https://github.com/Milbaxter/emergence-lab.git
cd emergence-lab
python3 -m emergence serve
```

Open **http://127.0.0.1:7331**. Choose **New mission**, enter a research direction, and set the maximum calls, research cycles, and deadline. Choose **Synthetic rehearsal** first if you want to inspect the workflow without inference.

For live research, install the [official Codex CLI](https://developers.openai.com/codex/cli), then sign in:

```sh
codex login
codex login status
```

Login must report **Logged in using ChatGPT**. The adapter was developed against CLI 0.155.1 and requires `--ignore-user-config`. Emergence Lab never reads or copies OAuth credentials. Codex owns authentication.

A finite mission can also run directly from your terminal:

```sh
# Fixed-response rehearsal; no model calls.
python3 -m emergence mission --provider demo --calls 12 --cycles 2

# Your subscription; up to 12 attempts across two research cycles.
python3 -m emergence mission --provider codex --calls 12 --cycles 2 --minutes 20 \
  --objective "Find and test a practical improvement to evidence-aware agent memory."
```

Add `--model MODEL_ID` to select an available model explicitly. Otherwise the Codex default is recorded as an unpinned alias. To choose a private data directory, put `--data-dir /path/to/lab` **before** `serve` or `mission`. The dashboard and CLI must use the same directory to share state.

## What agents can decide

| Stage | Autonomous decision |
|---|---|
| Scout | Select a narrow question, hypothesis, sources, baseline, and success criterion |
| Critic | Challenge confounds and propose a stronger experiment |
| Researcher | Write a Python experiment incorporating the critique |
| Critic | Inspect the executed code and receipt; write separate checks or an ablation |
| Critic after execution | Assess the observed verification result and accept or reject the scoped evidence |
| Coordinator | Accept, revise once, or retain an inconclusive result; choose the next question |

Agents see each other's messages and actual execution receipts. They can address a focused question to another role, which replies before the caller continues. There are at most two such consultations per cycle. The coordinator can request one revision, consuming the same finite call allowance.

This is a **designed research protocol with adaptive decisions**, not a free-form swarm. Roles run serially on the same subscription. There is no majority vote pretending that four roles are four independent people. Public enrollment, multiple workgroups, and on-chain governance are later stages.

The dashboard shows the mission, conversation, current question, calls and recorded tokens, generated code, executable evidence, findings, and amendment history. It updates while a mission runs. You can pause or stop at the mission level.

## Evidence and memory

An experiment is a standard-library Python program executed automatically in a separate workspace. Verification receives the actual program as `subject.py` and must add checks. The runner records code hashes, output, exit status, and limits.

A finding becomes **peer checked** only when both programs execute successfully, verification outputs `verified: true`, and both critic and coordinator accept. This is a workflow label, not proof of scientific truth: checks can be weak, leaked, or wrong. Unsupported conclusions stay provisional.

Recent non-retracted findings are supplied to subsequent turns and missions. Synthetic rehearsal memory is partitioned from live memory. Coordinators can retract or supersede claims they actually received, with an audit trail. Unsupported correction attempts are recorded as disputes without silently deleting checked knowledge. Dependency tracking and automatic reassessment of downstream claims are not implemented.

Source URLs are provenance, not proof of retrieval or truth. Scouts have Codex's built-in web search; available search events are retained. Other roles use supplied context. Long context is bounded; full records stay in SQLite and export. Programs should emit compact metrics with primary results first. The seeded research atlas remains a starting map, not a live state-of-the-art ranking.

## Subscription and resource limits

- Only `codex` (ChatGPT OAuth) and `demo` inference are supported. API-key login is rejected and API-key environment variables are removed. There is no billed API fallback.
- Subscription usage is real usage. A zero API-spend receipt does not mean zero tokens or unlimited access. Recorded token counters are displayed; this app cannot guarantee a token ceiling or read your remaining account allowance.
- The allowance is **attempts**, including failed or interrupted invocations. A request is reserved atomically before inference. Retries, consultations, and revisions consume the same allowance.
- One mission runner per data directory. Defaults: 12 attempts, two cycles, 20-minute scheduling deadline. A cycle needs at least six turns; revisions or consultations may leave room for only one cycle.
- Pausing/stopping or reaching the deadline prevents subsequent work once the current operation returns. An in-flight Codex request may finish and consume allowance. Stopping does not cancel a request at the provider.
- Provider errors pause the mission without silently resending the request. Restart recovery preserves recorded receipts and consumed slots. A manual resume is an exceptional mission-level action and may repeat the interrupted stage with a new slot; there is no exactly-once inference guarantee.
- `EMERGENCE_CODEX_TIMEOUT_SECONDS` sets each CLI subprocess timeout (default 180; range 15–600). A scheduling deadline can be exceeded by an already-running invocation.

The original $90/month cash ledger belongs to the manual job queue. Autonomous subscription missions use their separate call allowance; neither ledger measures remaining ChatGPT quota.

## Execution boundary

The Codex subprocess ignores user configuration, uses an empty temporary directory and a read-only sandbox, disables shell/apps/plugins/hooks/subagents, and returns structured text. Experiment execution is a separate component.

On macOS, a capability probe checks the native sandbox before generated code runs. Programs receive no inherited credentials or user environment, no network access, no child processes, and no access to personal file contents. Reads are limited to the Python runtime, required system files, and the experiment workspace; metadata permissions support Python startup. Writes stay in the workspace. There is no unsandboxed fallback.

Limits: eight CPU seconds, 12 wall seconds, 64 KB per output file, 128 workspace entries, and 2 MB workspace size. A 256 MB RSS watchdog is **best effort**, not a hard RAM boundary; sampling and disk checks can overshoot. Seatbelt is a deprecated native facility, not a VM. This pilot is for your own agents, not hostile public submissions. Public workers should use a validated disposable VM/container service with hard resource limits.

The localhost dashboard trusts local processes and uses Host/Origin checks; it is not multi-user owner authentication. Keep it on loopback. Agents cannot purchase resources, contact people, publish findings externally, or modify the application through their available tools.

## Research design and next experiments

The architecture draws on [AI co-scientist](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/), [AI Scientist-v2](https://arxiv.org/html/2504.08066v1), and [Agent Laboratory](https://arxiv.org/html/2501.04227v1). See [design notes and an evaluation plan](docs/autonomy-design.md) for what transfers to a subscription-sized pilot and what remains unproven.

The next scientific question is whether interaction helps **at matched resources**: compare one iterative agent, independent attempts, and this interacting team on fresh externally graded tasks. Log tokens and wall time, run multiple seeds, and remove shared memory or critic feedback in ablations. The existing four-task repair-selection suite is only a legacy smoke test and does not evaluate the new mission loop.

## Data and development

Private state lives in ignored `.emergence/`. Export includes the manual lab plus all mission prompts, responses, usage, messages, code, receipts, claims, and history. Inspect before sharing. JSON import is not implemented; back up the data directory with all runners stopped.

```sh
python3 -m unittest discover -s tests -v
node --check emergence/static/app.js
node --check emergence/static/missions.js
```

Tests use temporary state, fake inference, and local sandbox probes. They consume no model allowance. GitHub Actions remains an **inactive template** in `docs/ci-workflow.yml`; enabling it requires workflow-write permission.

The [legacy manual workflow](docs/manual-workflow.md) documents the earlier queue, ballots, and repair suite. It is retained for compatibility; use Missions for autonomous work.

MIT licensed.
