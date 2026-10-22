# The October 2026 pilot

## What it was

A one-off study run in October 2026, before any real data reached a network. Its purpose was to show that axis of travel
tuning could be made to appear, and be measured, in a constrained artificial setting, and to exercise every part of the
flow end to end. Its only output was a go or no-go decision. Everything was simulated with RatInABox in two worlds of
1 m by 1 m: a square loop (a ring corridor 0.25 m wide around a central hole, two east-west and two north-south segments)
and an open field. The loop agent was steered along the corridor, the open field agent moved as RatInABox gives it.

A vanilla tanh RNN of 128 units predicted the place cell population 0.5 s ahead. Three input sets were built: place cells
only (the primary arm), place cells with turn rate and speed, and place cells with head direction cells, turn rate and speed.
Only the place only arm was run, as the AGENTS.md text allowing simulated head direction in comparison arms was never added.
The design gave each input set trained networks on both worlds (5 seeds), trained on the open field only (5 seeds), untrained draws
(20) and a memoryless baseline. The thresholds in `thresholds.yaml` (direction, axis and arena tests, training checks and
the decision table) were written before any network was trained, their sha256 recorded, and never edited.

## What it found

Place only, 31 runs, all pilot observations under the rule 2 exception and not findings. Every training check passed: the
trained test loss at horizon 10 was 0.00326 against 0.00739 for clean persistence (0.44 times), position R2 from the hidden
state 0.985 (untrained 0.892) and heading R2 0.55 (untrained -0.005). Per trained seed there were 6, 8, 7, 15 and 6 axis
units on the loop, and 3.9, 4.7, 3.9, 9.4 and 3.9 percent of units were axis units released in the arena, against 0 for
the 95th percentile of the untrained draws and none in the raw place channels. The bar of 5 percent in every seed was
missed (four seeds at 5 units of 128). Only 9 of 42 axis units persisted in the arena. The open field only networks
released more axis units (10.31 percent against 5.16), a comparison confounded by the loop's place layout being new to
them. The decision line was No-go (row 6), not final, as the comparison arms were never run. The results note also says that
with place cell inputs the axis test cannot tell a unit with place fields on both parallel segments from an axis of
travel unit, that the steering made heading along the corridor 1.00 by construction, and that the networks had not
converged at 100 epochs.

## What the library took from it

`axis_of_travel_rnn` lifted from the pilot the vanilla RNN and memoryless models, the trainer with early stopping and the
persistence baseline, the dataset's scaler and leakage check, the direction, axis and arena tests with their pass level
permutation nulls, the population distances and decoders, and the figures. `thresholds.yaml` was copied unchanged into
the project's configs. Not lifted: the RatInABox worlds, the steering sweep, the study loop and the decision table. The
library reads the triple-T's corridor segments, not the loop's four, and whether the loop's thresholds carry over is
untested (docs/restructure/plan.md, debrief).

## Where it lives

The pilot's code, its 90 tests and its notebook are kept on branch `pilot`, at commit `d3bf79a`, in the `pilot/` folder
(see its README there). Its brief stayed in `tmp/documents/pilot.md`, outside git. Its run outputs were never committed.
