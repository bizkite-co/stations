---
status: deferred (stub — v1 holding rule only)
date: 2026-07-17
---

# 0004: Portable done_check execution model — deferred

## Context

[GLOSSARY § Portable task](../GLOSSARY.md#portable-task) defines the done_check as an
executable acceptance predicate — "the transform's watermark: anyone can re-run it to
verify completion without trusting the task's status field." External review (2026-07-17)
flagged the execution model as unspecified: invocation environment, result persistence,
flake handling, crash re-verification, file access scope.

## Holding rule (binds now)

A done_check is a shell command, run from the repository root of the task's
`transform.context`, exiting 0 iff the declared `output_type` state has been reached.
It MUST be side-effect-free and safely re-runnable at any time by any party — it is a
*measurement* of state, never a step that produces it. Consequently completion is
verified, not recorded: re-running the check after a crash, a flake, or plain suspicion
is always valid, and its result always outranks the task's own status field.

## Open questions for the full decision

- Environment declaration: how does a check state its dependencies (interpreter, tools,
  env vars) so a foreign worker can run it?
- Result persistence: is a passing run recorded anywhere (a witness record in a station?),
  or is the check always run live?
- Flake policy: retries, quorum of runs, or strict determinism required of the check?
- Access scope: may a check read outside the context repo (network, other stations)?
- Timeout and resource bounds.

Picked up when a second system consumes portable tasks mechanically; until then the
holding rule keeps checks honest (pure measurements) and portable in principle.
