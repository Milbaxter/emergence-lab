# Legacy manual workflow

This documents the original manual queue and coordination smoke suite. For autonomous missions, use the main README.

The long-term hypothesis is that useful collective intelligence can emerge from many interacting agents. This MVP makes questions, evidence, disagreements, execution, resource receipts, and reviews inspectable. It does **not** claim AGI or demonstrated emergent intelligence.

**Pilot:** one owner, four agent roles, local storage, OpenAI subscription inference through Codex OAuth, and off-chain advisory governance. No API keys, blockchain, token issuance, hosting bill, or automatic spending.

## Run it

Requires Python 3.11+ on macOS or Linux. The app has no Python runtime dependencies.

~~~sh
git clone https://github.com/milbaxter/emergence-lab.git
cd emergence-lab
python3 -m emergence serve
~~~

Open **http://127.0.0.1:7331**. Click **Run a free demo cycle** to rehearse a proposal, four synthetic ballots, a job, an artifact, and a separate critic review. The rehearsal uses fixed responses and no inference. Demo findings never count as accepted research.

State lives in the ignored **.emergence/** directory. Select another workspace with the global option before the command:

~~~sh
python3 -m emergence --data-dir /path/to/private/lab serve --port 7331
~~~

Server and workers must use the **same data directory**. Leave the server running in one terminal.

## Use your OpenAI subscription

Install the [official Codex CLI](https://developers.openai.com/codex/cli), then sign in with ChatGPT:

~~~sh
codex login
codex login status
~~~

The adapter requires a recent CLI with **--ignore-user-config** support; developed against **0.155.1**. Login must report **Logged in using ChatGPT**. Emergence Lab never reads or copies your OAuth tokens. Codex owns authentication.

1. Open a proposal in the dashboard.
2. Choose **Ask an agent**, select a role, and queue a $0 deliberation job.
3. In another terminal, run the corresponding role:

~~~sh
python3 -m emergence worker --agent critic --provider codex --once
~~~

The agent receives the proposal, discussion, prior ballots, source index, and accepted non-demo memory. It returns a structured advisory ballot and an artifact. You approve the proposal, queue research, and run a matching worker:

~~~sh
python3 -m emergence worker --agent researcher --provider codex --once
~~~

Each invocation handles at most **one job by default**. For deliberate polling, omit --once; it waits for one eligible job and exits after that job. Increase --max-jobs only intentionally.

**Subscription usage is real usage.** OAuth jobs consume your signed-in account's allowance. A $0 API-spend receipt does not mean zero tokens or unlimited access. The CLI's usage counters are retained when available. There is no API fallback or automatic purchase of credits.

The adapter forces ChatGPT login and the OpenAI provider, removes API-key environment variables from its child process, ignores user CLI configuration, uses an empty temporary working directory, a read-only sandbox, and disables shell, apps, plugins, hooks, browser, and subagent features. It produces text notes; it does not execute suggested experiments or browse cited pages. No OAuth credential enters the dashboard or exports.

**EMERGENCE_CODEX_TIMEOUT_SECONDS** optionally sets the subprocess deadline (default 180, allowed 15–600). This is not a hard token cap. A timed-out session may have consumed subscription allowance.

See official [authentication](https://developers.openai.com/codex/auth), [non-interactive execution](https://developers.openai.com/codex/noninteractive), and [configuration](https://developers.openai.com/codex/config-reference) documentation.

## What is implemented

| Area | Working behavior |
|---|---|
| Research atlas | Eight sourced starting points across the AI stack; add/search sources and evidence levels |
| Proposals | Hypothesis, baseline, evaluation, deliverables, project ceiling, discussion |
| Deliberation | Agent ballots through jobs; one current ballot per role; delegated ballots also supported |
| Governance | Advisory ballots, owner approval/rejection, project closure; all roles share one owner |
| Queue | Atomic claim, role matching, heartbeat, pause, cancellation, stopped-worker recovery |
| Memory | Accepted non-demo artifacts, recent discussion, and ballots supplied as bounded context |
| Findings | Text artifacts, provider metadata, resource receipts, downloads, separate reviewer identity |
| Accounting | Integer microdollars, atomic reservations, unknown-cost holds, ceiling at most $90/month; subscription counters stay separate |
| Experiments | Four workflows, deterministic repair-selection grader, immutable per-call JSON reports |
| Portability | SQLite persistence, JSON export, no hosted database |

The seeded atlas is a **source map**, not a continuously updated state-of-the-art leaderboard. Entries are marked source-reported, with limitations. A source URL supplied to an agent is not proof the agent read it.

## Coordination smoke suite

~~~sh
python3 -m emergence experiment --provider demo
~~~

This checks the plumbing using synthetic responses through the actual candidate mapper and grader. It compares:

- One agent revising its answer over four calls.
- Four independent answers with deterministic majority selection.
- Three independent proposals followed by one reviewer.
- Four calls with a shared notebook carried across tasks.

The public toy tasks select among fixed repairs for first-index lookup, chunking, median, and interval merging. The program never executes model-generated code.

To deliberately run the full suite on your subscription:

~~~sh
python3 -m emergence experiment --provider codex
~~~

**A complete run makes up to 64 Codex invocations.** The dashboard and tests never launch it automatically. All conditions have the same call cap; token consumption and latency can differ. Reports include raw outputs, usage, randomized task/condition ordering, seed, model alias, and limitations. Immutable reports live under .emergence/experiments/JOB_ID.json; --out additionally writes a convenience copy. Artifacts record the immutable path and SHA-256.

The tasks are public and small, model aliases can move, and a single run does not demonstrate general intelligence. Before scientific claims, add held-out tasks, pinned models, independent seeds, matched total-resource controls, memory ablations, and independent replication.

## Recovery and budget semantics

- Approving a project creates a ceiling; queuing a job reserves its allowance. These are not double counted.
- The ledger counts settlements in the UTC month of completion/manual settlement. All outstanding reservations carry across months.
- Cancelling a queued job releases its hold. Cancelling a running job requests a stop; a provider call may still finish.
- If a worker died, **stop it first**, then use **Recover stopped worker**. Execution becomes failed; any cash hold remains until manual settlement.
- Unknown cash cost differs from zero. Overruns are recorded fully and pause claims. Resume is blocked until commitments fit the ceiling.
- Completion receipts are idempotent; conflicting replays are rejected. The worker saves a private pending receipt before submission and replays that receipt on restart. It never automatically repeats inference.
- Creating proposals/jobs is not idempotent. Inspect the queue before retrying a lost enqueue response.
- Subscription jobs should have a $0 cash cap. The ledger is groundwork for later resource governance and does not enforce subscription quota.

## Trust and limits

This is a **trusted, single-user localhost application**. The owner interface uses loopback access and same-origin request checks. It is not an authentication boundary against another local program: local processes can act as the owner. Worker credentials scope normal worker requests; they do not create a multi-user security model.

Do not expose the server through a public tunnel. Public enrollment, distinct owners, Sybil resistance, contribution scoring, authenticated owner sessions, remote worker isolation, and federation are future work.

Separate agent review is not independent human replication. “Accepted” records a review decision, not a guaranteed true claim. Artifacts render as escaped text. Other agents' notes are untrusted evidence.

Exports contain research prompts and artifacts. Inspect them before sharing. Import/restore from JSON is not implemented. Back up the whole private data directory while the server is stopped.

## Development

~~~sh
python3 -m unittest discover -s tests -v
node --check emergence/static/app.js
~~~

Tests use temporary databases, loopback HTTP, fake Codex subprocesses, and synthetic inference. They consume no subscription allowance or API credits.

A GitHub Actions matrix for Python 3.11–3.14 is provided in **docs/ci-workflow.yml**. It is a template, not an active workflow. To enable it, an account with workflow-write permission can copy it to .github/workflows/checks.yml.

The code separates the SQLite state machine, HTTP server, worker, subscription adapter, grader, and static dashboard. The browser optionally exposes a WebMCP state and free-rehearsal tools when supported.

## Next milestones

1. Run a small real research cycle; inspect disagreement and review quality.
2. Add subscription-call allocation, private held-out suites, tool sandboxes, and agent-authored proposals.
3. Add independently authenticated contributors, signed provenance, and reputation based on reproduced work.
4. Add on-chain governance after the off-chain contribution rules survive actual use.

MIT licensed. Contributions should include a falsifiable question, reproducible evidence, resource accounting, and limitations.
