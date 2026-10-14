# Lab data clean plan

Read with spec.md. No code.

## Layout

    src/process_lab_data/
        __main__.py        the command line, the setup guards, the dry run, the summary, the exit code
        select.py          the funnel: sessions, epochs, blocks, with the counts per step
        frame.py           pixel scale, flip, rotation, translation, heading conversion
        labels.py          run, path_id, clean and phase per frame
        kinematics.py      the one versioned derivation of speed and turn rate (also used by synthetic data)
        output.py          write a block parquet, the blocks csv, the manifest
    src/axis_of_travel_rnn/trajectory.py   the schema and the loader that reads a block (real or synthetic)
    tests/unit/lab_data_clean/             small synthetic tables, no real data
    configs/local.example.yaml             CLEAN_LAB_DATA
    pixi.toml                              task clean-lab

## Data flow

Read the config. Load the four tables. Funnel the sessions and epochs (spec Selection), print
the count after each step. For each surviving epoch: load the session's frames, cut blocks at
pauses, gaps and the epoch bounds, drop short blocks. Fit the frame parameters per session and
epoch (spec Frame conversion). For each block: convert x, y and heading, derive speed and turn
rate, attach the labels, run the checks, write the parquet. At the end write the two blocks
csv files and the manifest. `--dry-run` stops after the funnel and prints what would be written.

## Order of work

1. Config key, pixi task, the skeleton with the funnel and `--dry-run`. This gives the real
   counts of sessions, epochs and blocks before anything else is built.
2. Frame conversion, checked by hand on a few sessions in the notebook (LED scale against the
   track extent, the heading sense on a known turn, the start site after translation).
3. Labels and kinematics, then the parquet and csv writers.
4. The loader in the core package, reading a block back into the schema.
5. Tests, then the full run by the author.

## Decisions

- Blocks, not runs, are the unit (spec Overview). Labels carry the runs.
- One derivation of speed and turn rate for real and synthetic trajectories, in the core package
  and versioned in the manifest, so statistics compare like with like.
- Native 60 Hz and metres on disk. No resampling, no cell encoding. The place cell encoding
  belongs to the model config, not the dataset.
- Frame parameters are fitted per session and per epoch and written down, never hard coded.
- Phase labels follow the first rule in the spec until the viewer says otherwise.
- Run once, write once, delete the folder to start over, as the converter does.

## Open questions

1. The heading sense in the camera frame (clockwise in the image is expected) and the room
   north offset: measured in the notebook, then fixed as constants.
2. Which path ids are returns: learned from the viewer before the phase rule is final.
