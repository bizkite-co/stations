---
status: deferred (stub — v1 holding rule only)
date: 2026-07-17
---

# 0003: Schema evolution — v1 freeze rule; migration policy deferred

## Context

[spec/PHYSICAL-CONTRACT.md](../spec/PHYSICAL-CONTRACT.md) §1.4 makes the schema sidecar's
field list normative for USV column order (P1): any add/remove/reorder/retype is a schema
version change. What it deliberately does not say is how a version change is *performed* —
flagged by external review (2026-07-17) as a real gap ("when a Pydantic model evolves, how
do old records transition?").

## Holding rule (binds now)

A writer MUST NOT change the field list of a station that has live readers. This is the
spec's v1 rule, restated here so the decision log carries it.

## Intended direction (not yet ratified)

The pattern already implies the answer: **schema evolution is a station transition, not an
in-place edit.** A new schema version is a new station (a versioned path or sibling), and
migration is an ordinary typed transform folding v1 records into v2 — whole-record,
replayable, inspectable mid-flight, like every other transform. No station's bytes are
ever reinterpreted under a changed sidecar.

## Open questions for the full decision

- Version marker placement: in the path (`…/v2/`) vs. in the sidecar only?
- The dual-write/dual-read window: who reads v1 while v2 fills, and when does v1 close?
- WAL replay across versions: must an index rebuild replay v1 segments through the
  migration transform, or are folded checkpoints re-based at migration time?
- Tombstoning the old station: when is deleting v1 an information loss vs. a time loss?

Picked up when the first real migration is needed; until then the holding rule prevents
the failure mode.
