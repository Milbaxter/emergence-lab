# Validation record — 2026-10-01

## Software checks

44 Python tests passed on macOS/Python 3.14.6. Coverage includes the mission cycle, direct consultations and their limit, atomic reservation, failed-call accounting, stop during inference, interrupted-run recovery, demo/live memory separation, verification gating, unsupported retractions, export routes, OAuth-only provider behavior, sandbox isolation, timeouts, output quotas, and legacy receipt recovery. JavaScript syntax checks passed for both dashboard scripts.

The native integration tests verified denial of outside file reads/writes, network connections, subprocesses, and forks. Generated code did not receive a test secret from the parent's environment. These are targeted controls, not a security certification.

## Live subscription pilots

Both pilots used the local official Codex CLI authenticated with ChatGPT. API spend reported by the adapter was zero; subscription usage was real. The model was the CLI default, not a pinned experimental model. No claim of a controlled coordination benchmark is made.

| Pilot | Recorded attempts | Outcome |
|---|---:|---|
| Status-aware evidence retrieval | 9 of 12 | Agents revised the protocol after criticism, recovered from a verification timeout through a smaller verification/reporting design, and recorded a provisional finding. This run exposed the missing post-execution critic assessment in the initial protocol. |
| Entity-aware retrieval and aliases | 6 of 8 | The corrected six-stage protocol completed without approval clicks. Experiment and verification executed, the critic assessed the observed result, and the coordinator recorded a peer-checked finding and next question. |

The first pilot recorded 135,870 input and 17,062 output tokens. The second recorded 82,261 input and 8,473 output tokens. These are CLI usage counters, not measured economic cost or remaining account quota. No additional autonomous mission remains running after validation.

The second pilot used 40 development and 160 held-out synthetic topics. The team reported that entity eligibility helped for resolvable names but abstained on every unknown or ambiguous alias. Its verifier reported 13,923 checks. These checks are agent-authored, same-owner checks; their count is not an independent quality measure. A constructed toy generator and the selection of eligible entities make these results narrow. They do not establish real-agent gains or emergent intelligence.

Raw local mission records, source code, execution receipts, and conversations remain in the private lab database and the dashboard export. They are not bundled into this public repository. A later change also ensures the post-execution critic receives both programs' full code in its bounded context; that context change was regression-tested rather than spending another live research run.

## Interface

The local mission dashboard was inspected in the browser, including the conversation, verification evidence, completed finding, usage, and mission setup form. A synthetic mission was launched through the form without model inference. The existing manual queue remains available separately.

## Limits and local development issue

The execution backend is currently macOS-only. Memory monitoring is best effort, not a hard VM boundary. Provider timeouts can consume subscription allowance, and independent evaluation of the research remains future work.

While developing the Seatbelt profile, rejected diagnostic profiles left several child processes stuck in macOS even after termination attempts. The corrected profile includes Python's required root-directory read, passes the capability/isolation probes, and completed the live experiments. Post-termination waits are bounded and there is no unsandboxed fallback. The older diagnostic processes had not cleared at the end of validation; a system restart may be needed to clear them. No restart was initiated automatically.
