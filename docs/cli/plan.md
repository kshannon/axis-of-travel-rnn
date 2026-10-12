# CLI implementation plan, PR 1

Read with spec.md. No code here.

## Architecture

    src/proj_helpers/
      paths.py                  repo_root(), configs_dir(), environments_dir()
    src/axis_of_travel_rnn/
      store.py                  resolve_store(), open_store(); Store: marker, layout, init, artifacts, counts
    src/cli/
      __init__.py               build_parser(), main(); GROUPS (name, one-line help); STUBS table
      _output.py                table(), lines(), emit(), fail(), not_implemented()
      store.py                  store init, store inspect
      env.py                    env list, env inspect
      artifacts.py              one list command, registered for datasets, models, experiments

Dispatch is the standard argparse idiom. Every command is `def cmd(args) -> int`
bound with `set_defaults(func=cmd)`; `main` calls `args.func(args)` and turns a
`StoreError` into exit 2. A group given without a command prints that group's
help and returns 1. Stubs are rows in one table, group, command and one-line
help, each bound to `not_implemented`, which prints the standard message and
returns 3.

Rule for later PRs: when a group gains a real command beyond `list`, it gets
its own module and its rows leave the stub table. The layout grows into one
module per group as the science lands, not ahead of it.

## Implementation order, this PR

1. Packaging and the package modules the CLI imports: pyproject with the
   console script, editable install through pixi, package init, environment
   builders, test package inits.
2. Store: resolution order, marker, layout, the manifest scan; `store init` and
   `store inspect`.
3. CLI package: root parser with `--store`, groups, the stub table, env and
   list commands, output helpers.
4. Tests: store logic, dispatch and exit codes, what the real commands print,
   every stub exits 3.
5. Docs: spec, this plan, tasks, README setup and reproduction commands.

## Key decisions

- argparse, standard idioms, no dependencies. Commands take the parsed args;
  no adapters and no docstring-to-help machinery.
- Stubs are data, not modules: fourteen rows in one table. Arguments are
  defined only when a command is implemented, in that command's PR.
- One list implementation serves the three artifact kinds, and one manifest scan
  in the store serves both listing and `store inspect`.
- Two locations, not one: configs from the checkout, artifacts from a store
  chosen by flag, environment variable, the machine-local `configs/local.yaml`,
  or default. A store is marked, and
  commands refuse unmarked directories, so an unmounted drive or a typo cannot
  produce a stray tree.
- Ids are derived from directories, never from an index file. A uuid and the
  input hash in every manifest give identity across stores; both arrive with
  the first writer.
- Recordings and analysis results live inside the model directory: three kinds.
- Module docstrings are one line between the quotes. Rationale lives in the
  spec and here, not in comments.
- Tests cover this project's logic only, not what argparse, pathlib or yaml
  already guarantee.
