# Data dictionary

Exact shapes and columns for the lab's variables and our tables are in docs/transform_lab_data/tables.md.

**60 Hz:** The camera takes 60 frames every second, so one frame lasts 1/60 of a second, about 17 ms.

**ACSF:** Artificial cerebrospinal fluid, the infusion with no drug in it. It is the comparison for muscimol, 5 sessions. The files only say ACSF.

**Agent:** A simulated rat. Its config sets its speed, how long it dwells at goals, which goal it picks next and how it moves. It holds nothing about neurons or the axis.

**Analysis file:** The file with rmaps in its name, one per session. It holds the lab's neural results plus their own labels, the segment stamps, the event list and the run markers. We read only the lab's labels from it, never the neural results. The event list gives every run, and the segment stamps give the epochs.

**Angles:** In the camera picture y points down, so positive angles turn clockwise on screen. Angles wrap into minus 180 to plus 180 degrees, so 179 and minus 179 are only 2 degrees apart.

**Annotations table:** A hand-written table, one row per session, that the converter never touches. It holds the reward rule, free notes and an exclude switch that leaves a session out of every statistic. We are still unsure what should set it.

**Artifact:** A saved result of the pipeline, which is a synthetic dataset, a trained model or an experiment. It is written once, named by an id and a content hash, and never changed in place.

**Artifact store:** The folder outside git that holds every artifact, marked by a store.yaml file. Lab data and the tables made from it never go in.

**Average and mashup light:** Two extra lights the lab added. The average light is the rounded midpoint and is missing when either light is missing. The mashup light is the average, or the one good light when only one is missing.

**Axis of travel:** The line the rat is moving along, where both directions on the line count as the same axis. Heading north and heading south are one axis. A cell tuned to it has two preferred directions about 180 degrees apart.

**Axis-of-travel tuning:** How much a unit's activity depends on the axis of travel. We look for a hidden unit with two direction peaks about 180 degrees apart that hold steady across places and sessions.

**Ballistic Runs:** A ballistic run goes from start to reward without stopping or backtracking. Whether the recorded sessions still include some learning is an open question.

**Baseline:** No manipulation, just a trained rat in an ordinary session. 76 sessions have no variant tag and are baseline. The arena and track parts of a rotation session carry the condition baseline too, but the session is not in the baseline set of 76. We fit statistics on the baseline set by default, so drugs, darkness and rotated tracks do not mix into the behavior we model.

**Bilateral and left:** The first part of the infusion tags. Bilat means both sides of the brain and left means the left side only.

**Camera frame and pixels:** Lab positions are camera pixels in a 640 by 480 picture, with y pointing down. Speeds are in pixels per second. We only have a rough scale of about 3.3 px per cm.

**Circular mean:** The average of a set of angles that handles the wrap, so 359 and 1 degrees average to 0, not 180. R, its length, is near 1 when the angles agree and near 0 when they spread all around.

**Circular standard deviation:** How spread out a set of angles is, in degrees, worked out from R. We call it the typical difference. With a sharp peak and long tails it overstates the spread.

**Clean and dirty run:** The labeler's judgment of a run, stored as the sign of its label. In the hand labeling tool TTPosTracker a person presses Clean Run or Dirty Run. In the automatic tool TTAutoPosTracker a run is marked dirty when the light's speed drops below 10 px/s inside it. So what clean means depends on which tool made the run. Nearly every indecision point sits inside a dirty run. About 27 percent of runs are dirty. We fit statistics on clean track runs, and dirty runs stay in the tables for comparison with real behavior.

**Click order:** The event list is in the order the labeler clicked, not in time order. 100 of 108 sessions are out of order as stored. We number runs by start frame instead.

**Condition:** What was being done during a part of a session, read from the file name. The values are baseline, rot45, rot90, dark and one for each infusion. It is a label, not a measurement. Every epoch carries one. The files do not say which parts were under a drug or in the dark, so a bilatmusc tag, for example, marks the arena, the track and the variant alike.

**Config:** A small YAML settings file under configs. The local config, configs/local.yaml, is the one file of paths for this machine and is never committed or hashed.

**Control experiment:** An experiment that tests another explanation, such as training in the open arena or shuffling data. If a control feeds the network something like heading, its config must say so.

**Dark:** A session run in the dark, with the tag `dark`. There is one, NS14_rec23. Its third part is the same maze, and the whole session counts as dark.

**Direction of travel:** The way the rat is actually moving, from the direction the midpoint of the lights moves between 3 frames before and 3 frames after, 6 frames or 0.1 s. It is not heading. It gets shaky when the rat is slow. Two opposite directions of travel make one axis of travel, so this is the quantity the axis is built from. Like heading, it never reaches training and is used only to analyze behavior and the network.

**Duplicate run:** A run labeled twice, with the same label and nearly the same frames. There are 5, probably from the automatic tool starting a run at every gate crossing.

**dvtFileName and dvtPathName:** The name of the tracker's original file that the lab started from, and the folder it sat in on the lab's computer. We do not read them as data. We only copy them into our record of the run, see Manifest (transformer).

**Environment:** A maze or arena described only by its shape, in a small config file. We have open_arena, triple_t, triple_t_rot90 and plus_maze, and triple_t_rot45 is still to come. It never means the software environment. Each one gets a short fingerprint of its shape, so a dataset can be traced to its exact geometry.

**Epoch:** A labeled part of a session, named by its role as arena, track or variant. It comes from one stamped segment, and it also carries an environment and a condition. Not to be confused with a training epoch, which is one pass over the training data. Epochs keep the arena and the track apart, which matters because the arena has no runs and can only give foraging statistics. The transformer keeps every epoch, and stage 2 drops any under 10 seconds, see The 10 second rule.

**Epochs table:** One row per epoch, with its environment, condition and where it starts and ends. Every stamp pair is kept, even a short one. It tells us which frames are arena, track or variant, so statistics can be fit on one environment at a time.

**Event:** One row of the event list. It has a frame row, a time and a label that says what it is. The labeling tool writes a run's start and end together as two adjacent rows, while indecision and reward marks are rows of their own. The time follows the tracking clock and jumps at a pause, so we place every event by its frame row.

**Events table:** Every row of the lab's event list as stored, in click order, with what kind of event it is and which run it belongs to. It lets us check every run against the rows it came from, including the indecision and reward rows that belong to no run.

**Experiment:** A population of model animals trained from one config, changing only one or two things at a time. Populations answer the question, single networks do not.

**Footprint and overlap:** A footprint is the set of 20 pixel squares the front light sat in for at least half a second during a segment. Overlap is how much two footprints share, from 0 to 1. Two halves of the same track session overlap 0.68 to 0.95, while the track against its rotated layout overlaps only 0.14 to 0.23. These are ranges we measured, not fixed cutoffs.

**Frame:** One camera picture, which is one row of the tracking file. Frames are numbered from 1 with no gaps, so a frame number is our clock. Run edges, epochs and events are all placed by frame number, never by time, because the time column jumps at a pause, see Pause.

**Frames table:** One file per session with one row per frame. It holds the light positions, heading, missing-sample flags, the painted label and the epoch. Missing positions are blank. It is the one Parquet file per session that the transformer writes, and stage 2 measures speed, direction of travel and the heading offset from it.

**Frozen model:** A trained network whose weights are fixed. We test it and record its hidden states without changing it.

**Goal:** One of the four reward sites where a route ends. Each side has an inner goal and an outer goal.

**Group:** The top folder a rat's files sit in, such as NS14Data or JL1HPCData. One folder is one rat.

**HDRadians:** The lab's heading, one value per frame, see Heading. We read it as stored and do not work it out again.

**Head-direction model:** A possible add-on that would give the simulated rat a head that can point away from travel, fitted from real data. It is not needed for the first milestone.

**Heading:** The angle of the line from the back light to the front light, in radians. It is where the light bar points, which may not always be where the nose points, see Heading offset. It is missing when either light is missing. The head is not exactly lined up with the bar, so heading has to be corrected before we compare it with travel. It stays in the data for validation and analysis and never reaches training.

**Heading offset:** The fixed angle at which the light bar sits on the head, found per recording. It is the circular mean of heading minus direction of travel over running frames. In JL1_rec23 it is about 105 degrees, so the bar sits nearly sideways. We subtract it from heading to get where the head points relative to travel, see Residual. It comes from the tracking alone, in the arena as well as on the track.

**Hidden state and hidden unit:** The hidden state is the set of numbers the network carries from step to step, and each number is a hidden unit. We treat a hidden unit like a recorded neuron, as an analogy only.

**Indecision point:** A spot where the rat seemed to hesitate, clicked by the labeler as its own event. There are 929, and almost all fall inside dirty runs.

**Infusion:** A session where fluid was put into the brain, either muscimol or ACSF. There are 12, all in NS14. The whole session counts as under the infusion, because the gap between the track and the third part is only 35 to 65 seconds. The files do not mark when the drug acted, so every epoch of an infusion session carries its condition, a label read from the file name and not a measurement.

**JL1HPC:** The folder name for rat JL1. HPC means hippocampus.

**Key counts:** 109 sessions from 4 rats. 76 baseline, 20 rotation, 12 infusion and 1 dark. 32 sessions have pauses, 6 have no stamps.

**Lab data:** The lab's MATLAB files from the Olson 2017 experiments. The lab data is transformed into, what we are calling, raw data.

**Lab filename protocol:** It reads rat, rec and the recording number, a date as month day year, three session digits, the kind of file and any tags. The tags come before or after the kind. We do not yet know what session digits other than 001 mean.

**Lab notebook:** The labnotebook folder, our own dated log. Coding agents never write in it.

**Label:** The number on an event. 1 to 98 starts a run on that path, the end is the same number plus 100, 0 is an indecision point and 777 is a reward. A minus sign means a dirty run. For example, 3 starts a clean run on path 3 and 103 ends it, while -3 and -103 mark a dirty run on the same path. The transformer pairs each start with its end by this number to build the runs.

**Labeling tools:** TTPosTracker is the lab's MATLAB tool for marking runs by hand with clicks for start, end, path, clean or dirty and reward. TTAutoPosTracker finds runs automatically, and a person then edits them. The segment stamps were clicked there too.

**LED:** One of two small lights on a rigid bar on the rat's head, which the camera follows. LED1 is the front light and LED2 is the back light. They sit about 17 to 20 pixels apart, so a pixel of jitter can swing the heading a few degrees.

**Lost, filled and unfilled samples:** A lost sample is a frame where the tracker lost a light. The lab filled gaps up to 30 frames, half a second, by interpolation and called those filled. Longer gaps stay unfilled, so a lost sample is filled or unfilled, never both. Filled samples are the lab's guesses, not measurements, so their flags stay in the frames table to tell them apart. In JL1_rec23 the front light is unfilled in about 8 percent of frames and the back light in about 24 percent.

**Manifest:** The record inside every artifact of how it was made, with seeds, configs, commit and lockfile. The converter keeps its own, see Manifest (transformer).

**Manifest (transformer):** The transformer's record of what it did, with versions, settings, the commit and a fingerprint of every lab file it read.

**masterTemplate and PathTemplate:** The lab's drawing of the track in camera pixels. masterTemplate is probably the outline the lab clicked, and PathTemplate probably holds one point per centimeter along each path, see True north. We do not read them, and stage 2 will use them to place the track, see Registration.

**maxGap:** The longest gap the lab filled by interpolation, 30 frames or half a second, see Lost, filled and unfilled samples. We read it into the sessions table and warn when it is not 30.

**Midpoint of the lights:** The point halfway between the front and back lights. We use it to measure direction of travel, speed and the heading offset. Which single point the network gets is still open. It sits a few centimeters ahead of the body.

**Missing stamps:** Six sessions have no timeStamps, five from JL1 plus NS14_rec14, so the converter gives them no epochs. Stage 2 may fall back on long tracked stretches, but NS14_rec14 has no safe fallback.

**Model animal:** One trained network, treated like one animal in an experiment. It has its own seed, manifest and checkpoints, saved copies from points in training. Failures are kept, because failures are results too.

**Muscimol:** A GABAA receptor agonist drug infused to reduce the activity of somatic action potentials. It shows up as musc in the tags bilatmusc and leftmusc, 7 sessions. We convert them but keep them out of the baseline set.

**Notebooks:** A Jupyter notebook in notebooks, one question each, made from a template and committed without outputs.

**nRealLights:** How many lights the tracker followed, which is 2, see LED. We read it only to check that it is 2.

**nRuns:** The lab's count of clean runs on each path, in the order of pathList, see Run markers. We read it only to check our clean runs against it, and it matched in all 108 sessions where starts and ends alternate.

**Occupancy and coverage:** Occupancy is how much time the rat spends in each small square of the room. Coverage is the share of squares it visited.

**Open arena:** A round platform, 60 cm across, set 20 cm above the middle of the track. Rats forage there for crumbs and no runs are labeled in it.

**Overlapping runs:** Neighbor runs that overlap by 1 to 6 frames. There are 11, in JL1_rec35, JL1_rec36 and NS15_rec15. Stage 2 will cut the earlier one so it ends a frame before the next starts.

**Painted label:** The lab's run label written onto every frame of a run, kept in the analysis file. A frame in no run gets 99. It matches the event rows to within 2 frames, median 0, in the four sessions we checked, which is how we know the rows are right.

**Path and path id:** A path is one numbered kind of run in the lab's labels, and the path id is its number. A session uses only some paths, for example 1 to 4, 9 and 10. How path ids map onto our four routes is still an open question.

**pathList:** The path ids used in one session, which differ from session to session, see Path and path id. We read it only to line up nRuns and runPosMarkers with their paths.

**Pause:** A spot where the camera stopped and restarted. The time column jumps by more than 0.1 s, sometimes by many minutes, while the frame numbers keep counting. 32 of the 109 tracking files have one, and we never treat the two sides as continuous. We never sample a trajectory across a pause, and a run with a pause inside it gets a flag, see Run flags.

**Perturbation experiment:** Switching off or adding noise to the axis-like units and seeing how much worse prediction gets, compared with other units. It shows whether they matter to the network, not to the brain.

**Phase:** A label on each frame or time step for what the rat is doing. For lab data it is run, between or forage. For synthetic data it is run, dwell, return or forage, where dwell is waiting at a goal or the start.

**pixelDvt:** A copy of the lab's cleaned tracking, one row per frame, with one more value on each row, the run label the lab painted on, see Painted label. We read only that painted label from it, and only when its frames and times match the tracking file.

**Plus maze:** A small plus-shaped maze with four 0.5 m arms, only for debugging. It is not in the paper.

**processedDVT:** The lab's cleaned tracking, one row per frame, with the frame number, the time and the positions of the lights, see Tracking file. We read it, taking the frame, the time, both lights and the extra lights, see Average and mashup light. A light the lab could not fill is stored as 1, see Sentinel value.

**Protocol:** A label for the whole session from its tag. It is standard, rotation, infusion, dark or other, where other means a tag we have not seen. It says what the session was meant to be, not what we measured. We use it to pick sessions, for example the baseline set is every session whose protocol is standard.

**Rat:** There are four, JL1, NS14, NS15 and NS16, with 14, 32, 33 and 30 sessions. The files also call it the subject. The paper names three rats, NS14, NS15 and NS16.

**Rat training:** Before recording, rats learned the track for 3 to 4 weeks until 80 percent of runs were ballistic.

**Rate map:** A map of how fast a neuron fires at each place. The analysis file is full of them.

**RatInABox:** The Python library we use to simulate agents. Its agent is a single point with no body, and its head direction is just its travel direction smoothed over 0.15 s.

**rawDVT:** The tracker's original output before the lab cleaned it, on the tracker's own number scale with 0 for a lost light, not in pixels, see Whole-number positions. The lab turned it into processedDVT. We do not read it.

**Registration:** Putting camera pixels onto the room frame with a scale, a shift, a rotation and maybe a flip, using the track itself as the target. Pooling sessions needs it. Stage 2 will do it.

**Resample:** Taking the 60 Hz tracking down to our time step, planned at 0.05 s, which is still not settled. Real and synthetic data go through the same function.

**Residual:** Heading minus direction of travel, after the heading offset is taken off. Zero means the head points where the rat goes. It averages to zero by design, so never use it to test whether the head follows travel. In our data the residual is within 30 degrees for about 70 percent of running frames on the maze, but only about a third in the arena. That is why we cannot treat head direction as equal to travel direction when we build synthetic trajectories.

**Return:** The trip from the goal back to the start around the outside edge of the track. Our drawing of the return corridors is inferred from the paper's figure.

**Reward:** Half a piece of Cheerio at a goal. In the arena the treat is a quarter Cheerio or crumbs.

**Reward rule:** Which goals pay out. NS14 got all-but-repeats, any goal except the one just visited. NS15 and NS16 got visit-all, where every goal pays once and it resets after all four.

**Room frame:** Our shared map for every environment, in meters, with the origin at the bottom left and north along y. All our environments sit in a 1.8 by 1.8 m room.

**Rotation:** A session whose third part uses the track turned 45 or 90 degrees about the room center. The tags plus45 mean 45 and plusquarter mean 90. There are 20, and the angle rests on the tag names until we register the track.

**Rotation control:** The triple-T turned 90 degrees about the room center. The room does not turn, so the same corridors now run along different axes. We keep it for validation, not training.

**Route:** One of the four ways from the start to a goal. We name it with two letters, the turn at the first T and the turn at the last junction, so ee, ew, ww and we. The middle turn is forced, so two letters are enough.

**Row 0 placeholder:** An event at frame 0 and time 0, which is not a real click. There are four, in NS16_rec31 and NS16_rec6, probably from relabeling with nothing selected. NS16_rec6 also has a dirty start with no end.

**Run:** One trip along the track from a start event to its matching end event, on one path. The lab labeled about 180 per session on average, clean and dirty together, 19,604 starts over 109 sessions. The paper's figure of about 80 counts rewarded runs only. The word also gets used for a training run, which is not this. It is the unit of behavior we model. Its edges come from frame numbers, never from times. The transformer keeps every run and only adds flags, and stage 2 drops duplicates and cuts small overlaps.

**Run flags:** Marks on a run that point out a problem and change nothing. They say if a run is a duplicate, how many frames it overlaps the previous run and if a pause falls inside it.

**Run markers:** The lab's own count of runs per path and the start and end of each run. They cover clean runs only. We use them to check our runs, not to build them.

**Running floor:** The speed above which a frame counts as running. The lab used 10 px/s, about 3 cm/s. We use 30 px/s for the heading offset, and the offset moves less than 2.3 degrees between the two.

**runPosMarkers:** The lab's start and end frame of each clean run, path by path, see Run markers. We read it only to check our clean runs against it. Its twin runTimeMarkers holds the same runs as times in seconds, and we do not read that one.

**Runs between stamps:** NS15_rec20 has about 37 runs in the 13,745 frames between its arena and track stamps. Maybe false starts, maybe a stamp problem. Those runs belong to no epoch.

**Runs table:** One row per paired run, numbered by start frame, with its path id and clean or dirty mark. Dirty runs are in it, and nothing is dropped at this stage. It is the starting point for the run statistics the generator needs, such as which path follows which. Its flags mark duplicates, overlaps and pauses, and stage 2 acts on them.

**sampleRate:** The camera's frames per second, which is 60, see 60 Hz. We read it into the sessions table and warn when it is not 60. The lab worked it out from the times at 2 rows near the start, so a pause there would make it wrong, see Pause.

**samplesLost, samplesFilled and samplesUnfilled:** The lab's flags for each light on each frame, saying it was lost, filled or left unfilled, see Lost, filled and unfilled samples. We read the filled and unfilled flags into the frames table and use the unfilled ones to blank the stand-in positions, see Sentinel value. We do not read samplesLost, since it is just the other two together.

**Seed:** The number that fixes random choices so a result can be repeated. Seeds are always explicit and never cherry-picked.

**Segment:** One stretch of a session that the lab marked with a start and an end. Segment 1 is the arena, 2 is the track and 3 is the variant part when there is one. No session has a fourth. Each segment becomes an epoch in our tables, see Epoch. Frames outside every segment belong to no epoch.

**Sentinel value:** A fake number that stands in for a missing one. An unfilled light is stored at position (1, 1). We trust the unfilled flag and turn those positions into blanks, never reading the pixel value. For example, a front light stored at (1, 1) with its unfilled flag set becomes a blank in the frames table. Read as a real position, it would put the rat in the top left corner of the picture.

**Session:** One recording of one rat on one day. A standard session is about 45 minutes, a few minutes in the open arena and then the track, where the paper counts about 80 rewarded runs. The lab labeled about 180 runs per session on average, clean and dirty together. We have 109 sessions. It is one tracking file plus one analysis file, and its session id ties every table row back to it.

**Session (lab):** In the lab's notes on timeStamps, segment 2 is called the first session and segment 3 the second session. For us a session is the whole recording.

**Session id:** The key on every row of every table, built from rat, recording, date and session digits, like NS16_rec32_20151103_001. We write the date year, month, day so it cannot be misread.

**Sessions table:** One row per session, with file facts and counts such as frames, pauses, events and runs. It is the first place to look before using a session, for example to see that it has a pause or no stamps.

**Shifted event times:** In 33 sessions some event times do not match their frame row. Almost all of it is just pauses, since event times follow the tracking clock. Only JL1_rec35 and JL1_rec36 have starts off by 0.5 and 0.3 s with no pause to explain it.

**Short arena:** In NS14_rec1, NS14_rec19 and NS16_rec10 the arena segment is only a few frames long. Stage 2 drops anything under 10 seconds, so those sessions have no arena.

**Spec, plan and tasks:** The three documents for each feature, in that order. The spec says what, the plan says how with no code, and the tasks are small steps of about one commit each. This follows (SDD) spec driven development when using AI agents to help develop code, create tests, etc.

**Speed:** How fast the midpoint moves, in pixels per second, over the same 6 frame step. For synthetic data it is in meters per second.

**spiral_events:** The lab's event list, one row for each click the labeler made. Every run we have comes from it.

**Split:** Dividing a dataset into train, validation and test parts. The validation part here watches training and stops it early, which has nothing to do with behavioral validation. One trajectory is never spread across parts.

**Subiculum:** A brain region. The Olson 2017 paper found neurons there that map the current axis of travel, and that is why this project exists. We do not simulate subiculum cells, only behavior and the network.

**Swapped field names:** In the lab's isRunningAnalysis output, the field called angVel holds speed and the field called vel holds turning rate. Read it by content, not by name.

**Synthetic dataset:** A saved set of synthetic trajectories built from one environment, some agents and a seed. A synthetic session is one simulated rat's block of runs, not a lab recording.

**Synthetic trajectory:** A made-up path of a simulated rat through an environment, at a fixed time step. The network trains on these.

**Tag:** The word in a file name that says what was special about the session, such as dark, bilatmusc or plus45. Capital letters vary, so we match without case. No tag, or just tt, means a standard session.

**The 10 second rule:** 600 frames. A segment shorter than this is not an epoch, and a tracking gap must be longer than this to count.

**timeStamps:** The lab's list of where each segment starts and ends, as start then end pairs. Despite the name they are frame numbers, not times. A baseline session has 4 numbers and a variant session has 6.

**Tracking file:** The file ending in ProcessedDVT, one per session. It holds where the rat's two head lights were in every camera frame, the lab's heading and flags for missing samples. It has no neural data. Every frame and every position we use comes from it, and the transformer turns it into the frames table.

**Tracking gap:** A stretch of more than 10 seconds where both lights are unfilled. Gaps often fall between segments, but some sit inside a segment, so they cannot mark edges on their own.

**Trajectory generator:** The code that makes synthetic trajectories, fit to real statistics such as speed, dwell and choices. Track runs can be fit by path, but the arena can only be fit as free foraging.

**Triple-T track:** The maze from the paper. Corridors are 8 cm wide and the whole track fits in a 1.60 by 1.25 m box. The rat starts at the middle of one long edge, runs up the stem, makes three turns and reaches one of four goals, a 1.40 m trip with turns at 0.51, 0.87 and 1.18 m.

**True north:** The lab's own fix for the light bar's mounting angle, worked out per recording from the north leg of two paths. It also contains the track's angle to the camera, so it is not the same quantity as our heading offset. We keep it only as a cross-check on the offset.

**Turning rate:** How fast the direction of travel changes. The lab calls it angular velocity, but it is about the direction of motion, not the head.

**Turning slope:** How the residual changes with turning rate near zero turning. A negative slope means the head lags behind the turn. It may be just geometry, since the midpoint sits ahead of the body, and we have not tested that.

**Units:** Stage 1 keeps the lab's units, pixels, seconds and radians. Synthetic data uses meters, seconds and radians.

**Variant:** A non-standard session, marked by a tag in the file name. Its third part comes after the arena and the track and is either the track under a drug or darkness, or a rotated track. 33 of the 109 sessions are variants.

**vel and acc:** The lab's own speed and direction of motion for each light, measured over 6 frames or 0.1 s, and acc is the same thing differenced once more. We do not read either, because stage 2 works out speed and direction of travel again from the positions, see Speed and Direction of travel. This vel is not the field called vel in Swapped field names.

**Whole-number positions:** The tracker's original output, rawDVT, used its own number scale with 0 for lost. The lab rescaled it to pixels and rounded every sample, so all tracking positions are whole numbers. We do not read rawDVT, see rawDVT.
