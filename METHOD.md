# Method: mapping an existing system onto the pattern

A repeatable procedure for pointing the [glossary](./GLOSSARY.md) at a system that wasn't
designed with it in mind, and having the mapping generate its own backlog. Run once per
consumer, producing that consumer's onramp doc in [consumers/](./consumers/).

Proven once so far: `task-agent`'s `docs/STATION-MAP.md` (pending ratification).

## Steps

1. **Enumerate the directories that hold records.** Not every directory — only the ones a
   process reads from or writes to as part of moving work forward. Ignore config, ignore
   vendored code.
2. **Classify each as a station.** For each: what record type lives there (even if
   implicit/undeclared today)? What serialization? Is there a version?
3. **Classify each consumer edge.** For every (consumer, station) pair, is the semantic
   queue, WAL, or index (see Trichotomy)? Write it down even when it's obvious — writing it
   down is what later reveals the same directory playing two roles to two consumers.
4. **Classify each transition.** What moves records between stations? Is it actually a
   pure typed function today, or does it silently do more (partial rewrites, hidden state)?
5. **List conformance gaps.** Anywhere the observed system violates an invariant from the
   glossary (single-writer rule, identity stability, whole-record transforms, watermark
   rebuildability) is a gap. Write each as a typed defect: which invariant, what breaks,
   concretely.
6. **Mark judgment calls.** Anything ambiguous (undeclared stations, dual-role logs) gets
   flagged for the system owner to rule on — don't resolve it unilaterally in the mapping.
7. **Split gaps into tasks.** Each accepted gap becomes one task in that system's own
   queue. The mapping doc generates its own backlog; it does not fix anything itself.
8. **State the falsifiability test.** What would prove this mapping wrong? (Usually: "when
   the reference implementation lands, refactoring this system to use it should require no
   on-disk change — if it does, the map was wrong.")

## Anti-patterns to flag during mapping

- A directory whose role can't be classified in one sentence — usually means two consumers
  are silently sharing a station with different assumptions.
- A "queue" with no claim mechanism — it's actually just a to-do list; fine, but don't call
  it a queue in the map.
- An "index" that isn't rebuildable from its source log by replay — it's actually
  independent state, which changes its failure mode (losing it loses information, not just
  time). Relabel it, don't force it into the index box.
