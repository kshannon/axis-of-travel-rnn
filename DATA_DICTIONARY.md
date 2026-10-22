# Data dictionary

What every attribute and term of the data means, in pipeline order: what the lab recorded (raw), what the converter makes of it
(transformed) and what the block step makes of that (built blocks). It defines meanings only. The files, their columns in order,
types and keys are in `docs/blocks_schema.md` for the block step and in `docs/transform_lab_data/tables.md` for the lab's files and
the transformed tables. Units are given with each entry: seconds (s), camera pixels (px) until registration, metres (m) in the room
frame after it, radians (rad) for angles unless an entry says degrees. A column name is written as code, a term in plain words.

## Raw: what the lab recorded

The Nitz lab's MATLAB files from the Olson 2017 experiments, read only, outside the repository (`LAB_DATA`).

| name | meaning, unit | from |
|---|---|---|
| lab data | The lab's MATLAB files, one tracking file and one analysis file per recording, 109 recordings from 4 rats. | the lab |
| tracking file | The file ending in `ProcessedDVT`: where the two head lights were in every camera frame, the lab's heading and the flags for missing samples. No neural data. | the lab |
| analysis file | The file with `rmaps` in its name: the segment stamps, the event list, the run markers, the painted run labels and the lab's neural results, which are never read. | the lab |
| rat, subject | One of four rats, JL1, NS14, NS15 and NS16, with 14, 32, 33 and 30 sessions. The paper names NS14, NS15 and NS16. | file name |
| group | The folder a rat's files sit in, such as `NS14Data` or `JL1HPCData` (HPC is hippocampus). One folder is one rat. | folder name |
| file name protocol | `<subject>_rec<N>_<MMDDYY><sss>[_tags]<kind>.mat`: rat, recording number, date month day year, three session digits, the kind of file and any tags before or after the kind. What session digits other than 001 mean is unknown. | file name |
| tag | A word in the file name saying what was special about the recording (`dark`, `bilatmusc`, `plus45` and so on), matched without case. None, or `tt` alone, is a standard recording. `turn` is only a naming suffix. | file name |
| variant | A recording with a tag. Its third segment is the track under a drug or in the dark, or a rotated track. 33 of the 109. | file name |
| rotation | A variant whose third segment is the track turned 45 degrees (`plus45`) or 90 degrees (`plusquarter`) about the room centre, 20 recordings. The angle rests on the tag names. | file name |
| infusion | A variant where fluid was infused into the brain, muscimol or ACSF, 12 recordings, all NS14. The whole recording counts as under the infusion, the files do not say when the drug acted. | file name |
| muscimol | A GABA-A receptor agonist infused to silence the region, tags `bilatmusc` and `leftmusc`, 7 recordings. | file name |
| ACSF | Artificial cerebrospinal fluid, the infusion with no drug, the control for muscimol, 5 recordings. | file name |
| bilateral, left | The first part of an infusion tag: both sides of the brain, or the left side only. | file name |
| dark | A recording made in the dark, tag `dark`, one recording (NS14_rec23). | file name |
| triple-T track | The paper's maze: 8 cm corridors in a 1.60 by 1.25 m envelope. The rat runs up the stem from the start, turns three times and reaches one of four goals, a 1.40 m run with turns at 0.51, 0.87 and 1.18 m. Geometry in `environments.triple_t` of `configs/project.yaml`. | the paper |
| open arena | A round platform 0.6 m across, 0.2 m above the middle of the track, where the rat forages for crumbs. No runs are labelled in it. The lab calls it the platform. | the paper |
| goal | One of the four reward sites a run ends at, an inner and an outer one on each side. | the paper |
| route | One of the four ways from the start to a goal, named by the turn at the first T and the turn at the last junction: ee, ew, ww, we. How the lab's path ids map onto routes is open. | this project |
| return | The way back from a goal to the start around the outside edge of the track. Its corridors are inferred from the paper's figure. | the paper |
| reward | Half a Cheerio at a goal, a quarter or crumbs in the arena. | the paper |
| reward rule | Which goals pay. NS14 all but repeats (any goal but the one just visited), NS15 and NS16 visit all (each goal once, reset after all four). | the paper |
| rat training, ballistic run | Before recording the rats learned the track for 3 to 4 weeks until 80 percent of runs were ballistic, start to reward without stopping or backtracking. Whether some learning remains in the recordings is open. | the paper |
| LED, front and back light | The two lights on a rigid bar on the rat's head that the camera follows. LED1 is the front light and LED2 the back, about 17 to 20 px apart, so one pixel of jitter swings the heading a few degrees. | tracking file |
| `nRealLights` | Number of lights tracked, 2. | tracking file |
| `sampleRate` | Camera frames per second, 60, so one frame is 1/60 s (about 17 ms). The lab computes it from the times at rows 99 and 100, so a pause there would corrupt it. | tracking file |
| camera frame, pixels | Lab positions are pixels in a 640 by 480 picture with y pointing down. Speeds are px/s. The rough scale is about 3.3 px per cm until registration. | tracking file |
| camera angles | In the camera picture y points down, so a positive angle turns clockwise on screen. Angles wrap into minus pi to pi. | tracking file |
| `rawDVT` | The tracker's original output, on its own integer scale (0 lost, up to 1023), not pixels. The lab rescaled it to pixels and rounded every sample, so all positions are whole numbers. Not read. | tracking file |
| `processedDVT` | The lab's cleaned tracking, one row per frame: frame number, time, both lights, and the average and mashup lights. A light the lab could not fill is stored as 1. | tracking file |
| `HDRadians`, head direction | The lab's heading per frame, rad, camera convention: the angle of the vector from the back light to the front light. NaN exactly where either light is unfilled. | tracking file |
| `samplesLost`, `samplesFilled`, `samplesUnfilled` | Per light and frame: the tracker lost it, the lab filled it by interpolation (gaps up to `maxGap`), or left it unfilled (longer gaps). Lost is filled or unfilled, never both. | tracking file |
| `maxGap` | The longest gap the lab filled by interpolation, frames, 30 (half a second). | tracking file |
| sentinel value | The stand-in an unfilled light is stored at, position (1, 1). Read as a position it would put the rat in the top left corner. | tracking file |
| average light, mashup light | Two lights the lab added. The average is the rounded midpoint, missing when either light is. The mashup is the average, or the one good light when only one is missing, missing when both are. px. | tracking file |
| `vel`, `acc` | The lab's speed (px/s) and direction of motion (rad) per light over 6 frames (0.1 s), and the same differenced once more. Not read, the block step derives its own. | tracking file |
| `timeStamps`, segment | Start and end rows of each recorded segment, as pairs, frame rows despite the name. Segment 1 is the arena, 2 the track, 3 the variant when present. Clicked by hand. Absent in 6 recordings (5 JL1 and NS14_rec14). | analysis file |
| session (lab) | In the lab's notes segment 2 is the first session and segment 3 the second. Here a session is the whole recording. | analysis file |
| `spiral_events`, event | The labeller's click record, one row per click: tracking row, time (s, following the tracking clock) and label. In click order, not time order. | analysis file |
| label | The number on an event. 1 to 98 starts a run on that path, the end is the start plus 100, 0 is an indecision point, 777 a reward click, 99 unlabelled (painted column only). A minus sign marks a dirty run. | analysis file |
| clean, dirty | The labeller's judgment of a run, the sign of its label. In TTPosTracker a person presses Clean Run or Dirty Run, in TTAutoPosTracker a run is dirty when the light's speed drops under 10 px/s inside it, so what clean means depends on the tool. About 27 percent of runs are dirty. | analysis file |
| path id | The lab's number for a kind of run. In the first track segment 1 to 4 are the outbound paths (start to a goal) and 9 and 10 the returns, the second segment adds 10 (11 to 14, 19, 20). A recording uses only some paths. | analysis file |
| `pathList`, `nRuns`, run markers | The path ids a recording uses, the clean runs per path, and the start and end rows (`runPosMarkers`) and times (`runTimeMarkers`) of the clean runs. Used only as a check. | analysis file |
| `pixelDvt`, painted label | The processed tracking with one more column, the run label painted onto every frame of a run (the later run where two overlap), 99 outside runs. | analysis file |
| indecision point | A hesitation the labeller clicked as its own event, label 0, 929 in all, nearly all inside dirty runs. | analysis file |
| reward click | Label 777, in only 5 of 109 recordings, the tool's reward code being commented out. Not used. | analysis file |
| labelling tools | TTPosTracker marks runs by hand. TTAutoPosTracker finds gate crossings inside the two track segments and a person edits them. The segment stamps were clicked there too. | the lab's MATLAB |
| `masterTemplate`, `PathTemplate` | The lab's drawing of the track in pixels, likely the clicked outline and one point per cm along each path. Not read. | analysis file |
| lab true north | Per recording, the mean raw heading on the north leg of paths 9 and 10 (template bins 90 to 100), rad. It contains the track's angle to the camera as well as the light bar's angle. | `ratTrueNorthCalculator` |
| lab running rule | Smoothed speed over 10 px/s (about 3 cm/s) and turning rate under 20 rad/s, both over 6 frames. Its output stores speed under `angVel` and turning rate under `vel`, read by content. | `isRunningAnalysis` |
| lab angular velocity | The turning rate of the direction of motion, rad/s, not of the head. | `isRunningAnalysis` |
| rate map | A neuron's firing rate by place. Never read. | analysis file |
| row 0 placeholder | An event at row 0 and time 0, not a real click, four in NS16_rec31 and NS16_rec6. NS16_rec6 also has a dirty start with no end. | analysis file |
| shifted event times | Event times that differ from their row's time, 33 recordings, nearly all from pauses. Only JL1_rec35 and JL1_rec36 have starts off by 0.5 and 0.3 s that no pause explains. | analysis file |

## Transformed: what the converter makes

`pixi run transform-lab-data` writes the lab's data as tables at the native rate in pixels, a conversion only (`TRANSFORMED_LAB_DATA`).

| name | meaning, unit | from |
|---|---|---|
| `session_id`, session | One recording of one rat on one day, about 45 minutes, a few in the arena then the track. The id joins subject, rec, date (year month day) and session digits, like `NS16_rec32_20151103_001`, and is on every row. | file name |
| `subject_id`, `rec`, `date` | The rat, the recording number, and the recording date as YYYY-MM-DD. | file name |
| `dvt_file`, `rmaps_file` | The tracking and analysis file names. | file names |
| `protocol` | The whole recording's label from its tag: `standard`, `rotation`, `infusion`, `dark` or `other` (an unseen tag). The baseline set is every `standard` recording, 76. | tag |
| `condition` | The manipulation in force during an epoch: `baseline`, `rot45`, `rot90`, `musc_bilateral`, `acsf_bilateral`, `musc_left`, `acsf_left`, `dark`, or an unknown tag verbatim. A label from the file name, not a measurement, so an infusion tag marks every epoch. | tag |
| baseline | No manipulation, a trained rat in an ordinary session. The arena and track of a rotation recording are `baseline` too, though the recording is not in the baseline set. | tag |
| `epoch` | A labelled part of a session from one stamped segment: `arena`, `track` or `variant`. Not a training epoch. Frames outside every epoch are dead time. | `timeStamps` |
| `environment` | The geometry an epoch maps to: `open_arena`, `triple_t`, `triple_t_rot45` or `triple_t_rot90` (the last two still to add). Never the software environment. | tag |
| `rate_hz` | The lab's `sampleRate` rounded, Hz, 60. | `sampleRate` |
| `max_gap` | The lab's `maxGap` rounded, frames, 30. | `maxGap` |
| `n_frames` | Frames in the recording, `n_frames / rate_hz` its recorded time. | tracking file |
| pause | Where the camera stopped and restarted: a step in `t` over 0.1 s, sometimes minutes, while frame numbers keep counting. 32 of 109 recordings have one. Nothing is sampled across it. | tracking `t` |
| `n_pauses`, `paused_s` | The pauses in a recording and the time they skip, s (each step minus 1/60 s, summed). | tracking `t` |
| `unfilled_front`, `unfilled_back` (sessions) | Fraction of frames with that light unfilled. | `samplesUnfilled` |
| `n_events`, `n_runs` | Events and runs of the recording. | `spiral_events` |
| `frame` | One camera picture, one tracking row, numbered from 1 without gaps. Runs, epochs and events are placed by frame, never by time. | tracking file |
| `t` | The lab's timestamp, s, as stored, jumping at a pause. | tracking file |
| `front_x`, `front_y`, `back_x`, `back_y` | LED1 and LED2, px, NaN where unfilled (the sentinel blanked by its flag). | `processedDVT` |
| `head_dir` | The lab's heading as stored, rad, camera convention. | `HDRadians` |
| `filled_front`, `filled_back` | The lab interpolated that light on this frame, a guess and not a measurement. | `samplesFilled` |
| `unfilled_front`, `unfilled_back` (frames) | That light is missing on this frame. | `samplesUnfilled` |
| `painted_label` | The lab's painted run label of the frame, 99 unlabelled, blank when the file's `pixelDvt` does not match the tracking. | `pixelDvt` |
| `avg_x`, `avg_y`, `mashup_x`, `mashup_y` | The lab's average and mashup lights, px, NaN where missing. | `processedDVT` |
| `frame_start`, `frame_end` | First and last frame of an epoch or run, 1-based, inclusive. | `timeStamps`, events |
| `t_start`, `t_end`, `duration_s` | The tracking times at those frames, s, and the frame count over `rate_hz`, s. | tracking `t` |
| `run`, run | One trip along the track from a start event to its matching end, on one path, numbered from 1 in start frame order. About 180 per recording, clean and dirty together. The paper's 80 or so counts rewarded runs. Not a training run. | `spiral_events` |
| `path_id` | The run's path id, the absolute value of its start label. | label |
| `clean` | The labeller's judgment, the sign of the start label, copied and never computed. | label |
| `duplicate_of` | An earlier run with the same signed label that this one overlaps by half the shorter or more, a flag. 5 in the data. | events |
| `overlap_frames` | Frames the previous run reaches into this one, a flag. 11 overlaps of 1 to 6 frames, in JL1_rec35, JL1_rec36 and NS15_rec15. | events |
| `spans_pause` | A pause falls inside the run, a flag. | `t` |
| run flags | `duplicate_of`, `overlap_frames` and `spans_pause`: they point out a problem and change nothing. | converter |
| `event`, `kind` | An event's place in click order, and what its label makes it: `start`, `end`, `indecision`, `reward` or `other`. | `spiral_events` |
| runs between stamps | NS15_rec20 has about 37 runs in the 13,745 frames between its arena and track stamps, in no epoch. | `timeStamps` |
| short arena | In NS14_rec1, NS14_rec19 and NS16_rec10 the arena segment is under 10 s. | `timeStamps` |
| tracking gap | A stretch where both lights are unfilled for long. The transform docs give 10 s for finding segments, the block step cuts at any gap over `max_gap` frames (built blocks, cut point). | `samplesUnfilled` |
| `reward_rule`, `exclude`, `notes` | Annotations made by hand per recording: the reward rule, leave out of every statistic, free text. | by hand |
| transformed stamp | The `run.timestamp` of the converter's manifest, the version of the transformed folder a review and a build name. | converter |
| check status | `pass`, `warn` or `fail` of each check of each recording. | converter |
| heading offset | The fixed angle of the light bar on the head per recording, rad: the circular mean of heading minus the direction of motion over running frames. About 105 degrees in JL1_rec23, so the bar sits nearly sideways. Computed in the block step as the LED offset. | tracking file |
| true north | The lab's per recording fix for the bar's angle (raw, lab true north). It also holds the track's angle to the camera, so it is only a cross-check on the heading offset. | analysis file |
| circular mean, R | The mean of angles that respects the wrap (359 and 1 degrees average to 0), and its length R, near 1 when the angles agree and near 0 when they spread. | method |
| circular standard deviation | The spread of angles from R, degrees. With a sharp peak and long tails it overstates the spread. | method |
| footprint, overlap | The 20 px squares the front light sat in for at least 0.5 s during a segment, and the share two footprints have in common, 0 to 1. Two halves of a track overlap 0.68 to 0.95, a track against its rotated layout 0.14 to 0.23. | validation by hand |

## Built blocks: what the block step makes

`pixi run build-blocks --blueprint <name>` cuts, registers and labels the transformed frames into blocks in the room frame at the
lab rate (`PROCESSED_LAB_DATA/<name>/`). Rules and settings are named by their key and default.

| name | meaning, unit | from |
|---|---|---|
| blueprint | The entry of the project config that says which blocks a build makes: sessions, rule and setting overrides, start offsets, the reviews folder and the expected data id. | `blueprints` in `configs/project.yaml` |
| format version | The review tool's format version the reviews and blocks follow, recorded, not checked. | blueprint |
| review | A person's decisions on one session: the kept blocks, cuts, flagged runs, exclusion, start offset and notes. | the review tool |
| `reviewed_by`, `reviewed_at` | Who saved the review and when, ISO time. | review |
| review stamp | The review's `reviewed_at` and the transformed stamp it was made against. | review |
| excluded | The person left the whole session out, it builds no blocks. No rule excludes by tag. | review |
| flagged run | A run the person left out of the labels, its frames taking run 0. | review |
| funnel | Which sessions the rules allow (an epoch of the kinds in `epochs` under `condition` baseline, frames present) and why the others are not. | rules |
| cut point | Where a stretch ends: an epoch start, a pause (step in `t` over `pause_step_s` 0.1 s), a jump (mashup moves over `jump_px` 40 px in one frame) or a tracking gap (`gap_lights` both unfilled for over `max_gap` frames). | transformed frames |
| stretch | A run of frames in one epoch between cut points, trimmed by the margins. The range a block edge may move within. | rules |
| margin | Frames trimmed inward from a stretch edge beside a pause, jump or epoch bound, `pause_margin_s` 5 s. | rules |
| block, `block_id` | A stretch of one epoch of at least `min_block_s` 10 s with no pause, jump or long gap inside, kept by the person. Its id is `{session_id}_{epoch}_{NN}`, NN counting the epoch's blocks from 01 in frame order, dropped ones included. | rules and review |
| cut | A frame range the person removed from the blocks it touches, a piece left under `min_block_s` dropped. | review |
| snap | A moved block edge within `snap_s` 1 s of a run's start or end snaps to it. | rules |
| `status` | A block's state in the review: `auto` (as the rules made it), `confirmed`, `edited` or `dropped`. The build keeps `confirmed` and `edited`. | review |
| room frame | The shared map, m: a 1.8 by 1.8 m room, origin bottom left, x east, y north. | environment yaml |
| registration | Taking pixels to the room frame per epoch kind: flip the camera's y, divide by the scale, rotate by the track rotation, shift by the offset. | transformed frames |
| `scale_px_per_m` | Pixels per metre. The track's is the mean of two axis estimates (`scale_x_px_per_m`, `scale_y_px_per_m`), each the span of the outer occupancy peaks of the running frames over the centreline's extent. The arena's is the track's times the parallax ratio. | registration |
| parallax ratio | (camera height minus track height) over (camera height minus arena height), from `camera_height_m` 2.6, `track_height_m` 0.2 and `arena_height_m` 0.4. The arena floor is nearer the camera. | rules |
| `rotation_rad`, rotation concentration | The counterclockwise rotation that lays the track's corridors along the room axes with the start below the goals, rad, used for both kinds, and the four-fold concentration of the running directions, 0 to 1. | registration |
| flip | The camera's y negated, always true. | registration |
| `offset_m` | The shift that lands the anchor, m: the start site on the track, the arena's median position at the room centre. | registration |
| start site, goals | The median position at the outbound runs' first frames and at their last frames, px. | registration |
| start offset, `start_offset_m` | How far up the stem the start site sits above the bottom return corridor, m. The person tunes it in the review, a blueprint may set it per session, null means the environment yaml's (0). | review, blueprint |
| start offset measured | The same distance read from the running frames, m, a check. | registration |
| LED separation | The distance between the two lights in metres at the kind's scale, warned when outside `led_separation_m` 0.04 to 0.08. `nominal_led_separation_m` 0.05 is the paper's, used for the still floor. | registration |
| LED offset, `led_offset_rad` | The heading offset of the session, rad, with its concentration `led_offset_r` and the running frames used `led_offset_n`. | transformed frames |
| arena extent ratio | The arena's occupancy extent between `extent_percentiles` 1 and 99, in metres, over the arena's size, 1 when the rat covers it. | registration |
| `x`, `y` | The mashup light in the room frame, m. | registration |
| direction of travel | The direction the mashup moves over `speed_smooth_frames` 6 frames (0.1 s), rad. Not heading. Shaky when the rat is slow. Never reaches training. | transformed frames |
| axis of travel | The line the rat moves along, both directions on it the same axis, so north and south are one axis. A unit tuned to it has two preferred directions 180 degrees apart. The quantity the project looks for and never gives the network. | direction of travel |
| running | A frame whose speed exceeds a floor. Open: the engine's rules say `running_px_per_s` 20 px/s (LED offset and registration), the transform docs say 30 px/s for the heading offset, and the lab used 10 px/s. The offset moved under 2.3 degrees between 10 and 30 px/s. | rules |
| still | A frame whose steady speed is under `running_floor_m_per_s` 0.03 m/s at the nominal scale. Used for held heading and pauses. | rules |
| `heading` | The head direction in the room frame, rad, counterclockwise from east (north is pi over 2), wrapped to minus pi up to pi: the lab's heading negated, minus the LED offset, plus the track rotation. Where the head points, not where the rat goes. NaN where lost. | `head_dir` |
| `heading_filled` | Heading filled along the shortest arc across a gap of up to `heading_fill_s` 3 s. | rules |
| `heading_held` | Heading held at its last measured value across a longer gap while the rat is still throughout. | rules |
| heading lost | Heading missing after fills, a gap that touches an end of the recording, holds a pause, or is too long while the rat moves. | rules |
| residual | Heading minus direction of travel after the LED offset, rad. Zero mean by construction, so never a test of whether the head follows travel. Within 30 degrees on about 70 percent of running frames on the maze, about a third in the arena. | heading |
| `speed` | Savitzky-Golay derivative of `x`, `y` over `smooth_window_s` 0.15 s at order `smooth_order` 2, within the block alone, m/s. NaN where position is missing. | `x`, `y` |
| `turn_rate` | The same derivative of the unwrapped measured heading, counterclockwise positive, rad/s, the head's angular velocity. NaN where heading is not measured (lost, filled, held). | `heading` |
| turning slope | How the residual changes with turning rate near zero, a negative slope meaning the head lags the turn. Possibly geometry alone, untested. | analysis |
| `kinematics_version` | The version of the speed and turn rate derivation, 1. | rules |
| `n_lights` | Lights not left unfilled on the frame, 2, 1 or 0. | unfilled flags |
| `filled_front`, `filled_back` (blocks) | The transformed flags, copied. | transformed frames |
| `phase` | One label per frame, the first that applies: `forage` on every arena frame, `pause` in a run where speed stays under the still floor for over `pause_min_s` 1 s, `outbound` or `return` in a run whose path id is in `outbound_paths` (1, 2, 3, 4) or `return_paths` (9, 10), `dwell` on every other track frame. Replaces the transform docs' run and between. | runs, speed |
| `trip` | An outbound run, the dwell at the goal, the return and the dwell at the start, from one outbound start to the next or the block end. Positive and numbered when complete, negative when partial, 0 in the arena. | runs |
| `run` (blocks) | The transformed run number owning the frame, 0 outside runs. The later run owns overlapping frames, duplicates and flagged runs are left out. | runs |
| `path_id` (blocks) | The owning run's path id, 0 outside runs. | runs |
| `clean` (blocks) | The owning run's `clean`, false outside runs. | runs |
| `n_runs`, `n_clean_runs`, `n_trips`, `n_complete_trips` | Counts per block of runs, clean runs, trips (partial included) and complete trips. | labels |
| `heading_lost_s`, `heading_filled_s`, `heading_held_s` | Time per block with heading lost, filled and held, s. | heading |
| `kind` | The block's epoch kind, `track` or `arena`. | epoch |
| warning, failed, skipped, error | A warning flags a session (scales that disagree, LED separation out of range, reviewed under other rules). A failed block is not written (position not finite, irregular steps in `t` beyond `t_step_tolerance_s`). A skipped session had no review or is outside the funnel. An error is a session whose build raised. | build |
| code version, engine version | `blocks <engine version> <short commit>` with `+dirty` for uncommitted changes, and the engine's own version, 2. | build |
| data id | The sha256 over `blocks.csv` and every block parquet in block id order, each file's path and its bytes' sha256. Same blocks, same id, on any day. It hashes bytes, so a different pyarrow can change it while values stay equal. | build |
| expected data id | The data id a build of the blueprint must give, written in after the first build. | blueprint |
| window, `window_s` | A stretch of a block the network sees, 40 s by default (settings). | settings |
| `stride_s`, `burn_in_s`, `horizon_s` | The step between window starts (10 s), the steps at a window's start not scored (1 s) and how far ahead the position is predicted (0.5 s). | settings |
| `rate_hz` (settings), resample | The rate training takes every k-th frame to, 20 Hz (0.05 s), recorded only by the build. | settings |
| verdict | Whether a block gives windows at the settings, and the reasons when not: no window fits, heading measured under `min_heading_measured` 0.8, complete trips under `min_complete_trips` 1. | settings |
| split | Train, validation and test by whole recording dates, shuffled by the seed. Validation stops training early, unrelated to behavioural validation. | experiment config |
| inputs | The block columns an experiment gives the network (`inputs.columns`): `x`, `y` (the control), and optionally `speed`, `heading` (as its sine and cosine) and `turn_rate`. Standardised by the training blocks' mean and sd except the sine and cosine. The target is always future `x`, `y`. `phase`, `trip`, `run`, `path_id`, `clean` and any axis label never reach training. | experiment config |
