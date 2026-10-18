# RatReplay rebuild plan

Read with `architecture.md`, which is the spec. No code here. This is the project design: what is built in
what order, what depends on what, where the critical path runs, and three options for the author to pick
from.

## Shape

Build by layers (architecture.md, Migration): utilities, then accesses, then engines, then managers and
routers, then pages, then the system tests. Most of the first two layers exist and are renamed and merged,
the engines are where the science moves in, the managers regroup, the pages adapt. By layers is right for
a project this small: it keeps one builder on one layer at a time and the integration points are few, at
the cost of each layer going critical, which the options below handle with float.

Two slices run through those layers. The real slice (ReviewManager, ValidationManager, their pages) is the
critical path and is used on real data as soon as it works. The synthetic slice (GeneratorEngine,
SyntheticAccess, SynthesisManager, the Synthetic page) depends only on the engine contract and the
accesses, so it has float and can run in parallel or after.

## Network

Estimates are coarse, in builder sessions (one session is a focused half day including its tests),
accuracy over precision. Letters are the tasks in `tasks.md`.

    U1 utilities (config, tables, arrow, clock, paths, ids, errors)                 1
    A1 TransformedAccess                                   after U1                 1
    A2 ProcessedAccess (review, blocks, metadata, windows.json)   after U1          2
    A3 EnvironmentAccess                                   after U1                 0.5
    A4 SyntheticAccess                                     after U1                 1
    E0 engine contract: signatures and the rules and settings objects, written first   after U1   0.5
    E1 TrajectoryEngine.session (kinematics, heading, cuts, spans, occupancy, initial blocks)   after E0, A3   2
    E2 TrajectoryEngine.apply (edit rules, parity with the old tool)   after E0    1
    E3 TrajectoryEngine.blocks (labels, metres, 20 Hz, parity with the processor)   after E1   2
    E4 TrajectoryEngine.windows (rows, verdicts)           after E0                 1
    E5 TrajectoryEngine.recipe                             after E3                 1
    E6 GeneratorEngine                                     after E0, E5             2
    M1 ReviewManager + router                              after A1, A2, E1 to E4   2
    M2 ValidationManager + router                          after A1, A2, A4, E4     1.5
    M3 SynthesisManager + router                           after A2, A4, E5, E6     1.5
    L  layering test and composition root                  after M1                 0.5
    F1 frontend: api client, state, Data and Sessions pages   after M1, M2          1
    F2 Replay page on ReviewManager                        after F1                 2
    F3 Blocks and Windows pages on ValidationManager, Select settings   after F1    1.5
    F4 Synthetic page                                      after M3, F1             1
    F5 cut the Vitest and Playwright suites to the layout, move them   after F2, F3   1
    S1 system tests: save blocks, rebuild all, health, readiness   after M1, M2, L   1
    S2 Playwright flows (two or three)                     after F2, F3             1
    R1 README, pixi tasks, remove dead code paths in the tool   after S2            0.5
    K  Kyle builds a real dataset, reports                 after R1                 (Kyle)
    R2 remove src/process_lab_data, old src/ratreplay, lab_blocks.yaml   after K    0.5
    D  debrief                                             after R2                 0.5

Critical path: U1, A2, E0, E1, E3, M1, F1, F2, F5, S2, R1, K, R2, D. About 17 sessions of builder time
plus Kyle's run. Everything on the synthetic slice (A4, E5, E6, M3, F4) and E2, E4, A1, A3, M2, F3, S1
has float against it.

God task watch: TrajectoryEngine is split into six (E0 to E5) so that no single task hides the move of
the science. E1 and E3 are the two largest and carry the parity tests, they are where the plan slips if
it slips.

Risk, Löwy's criticality model (critical 4, low float 3, medium 2, high 1, over 4N): 14 critical tasks,
7 with low to medium float, 5 with high float, about 0.73. That is inside the acceptable band (0.3 to
0.75) but above the 0.7 a normal solution should stay under, which is the usual price of building by
layers, and the reason the recommendation below is the decompressed option.

## Options

- **Normal.** One builder, by layers, in the order above. About 17 sessions on the critical path, the
  synthetic slice built in the gaps. Risk moderate: the engine layer is critical by construction, the rest
  has float.
- **Compressed, about 25 percent.** Two builders after E0: one on the real slice (E1, E3, M1, F2), one on
  the synthetic slice (E5, E6, A4, M3, F4) and the off path tasks (E2, E4, A1, A3, M2, F3). Enabling
  work: E0 becomes a real contract design task with fakes, and an integration task joins the two before
  S1. About 13 sessions, higher cost (two builders, the integration task) and more for the reviewer to
  hold at once.
- **Decompressed.** Normal, with the synthetic slice deferred until K (the first real dataset) has
  happened. The real slice reaches Kyle sooner and nothing synthetic is built on an engine contract that a
  real dataset might still change. About the same total, longer calendar, lowest risk.

Chosen 2026-10-17: decompressed. The engine contract is the thing most likely to move once real blocks
are looked at, and the synthetic slice is the thing most exposed to that move. So the order is: U1, A1,
A2, A3, E0 to E4, M1, M2, L, F1, F2, F3, F5, S1, S2, R1, then K (Kyle's first real dataset), then the
synthetic slice A4, E5, E6, M3, F4 with its tests, then R2 and D.

## Quality in the plan

Service level tests are inside each task's estimate (unit tests for the engines, an integration file per
manager). S1 and S2 are the system tests. The layering test (L) runs with every commit. Every pass is
reviewed by Opus against architecture.md before it is committed. Parity with the old processor and tool
(E2, E3) is kept until R2 removes them. D is the debrief, with the six headings in architecture.md's
checklist source: estimation accuracy, design efficacy, individual and team work, issues to avoid,
recurring problems, commitment to quality.

## What is not in this plan

Training. The converter joining RatReplay. Moving `ratreplay/` under `src/`. The Compare game. A second
client.

## Notes from the build, for the tasks ahead

- A1: `TransformedAccess.health()` assumes a root. The "key not set in local.yaml" message belongs to the
  composition root and ValidationManager (tasks L and M2), not to an access. `sessions()` returns the
  ids of the sessions with frames so ReviewManager.index (M1) does not call `session()` per row. The
  schema parity test against `contract.py` goes when L deletes `contract.py`.
- A2: the build records per block the window count and verdict at its settings in the session metadata
  (informative, readiness recomputes). The rename pass is the one window where a crash leaves a loud
  mixed state, health names it (missing, orphan and temporary files). For M1: `date` from the
  transformed sessions table is a date and the csv column is text, so the build writes `str(date)`.
  The access does not check edits (EDIT_FIELDS is description only), `TrajectoryEngine.apply` refuses
  unknown ops (E2). For M2: add a `built()` verb (sessions with metadata, including those with zero
  blocks) and an arrays-only read if readiness over all blocks is slow.
