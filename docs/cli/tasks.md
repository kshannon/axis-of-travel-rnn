# CLI tasks, PR 1

One commit per task on `feature/cli`, each verified by `pixi run test` plus the
listed command. The branch is squashed on merge; this list is the logical trail.

- [x] T1 Spec, plan and tasks under `docs/cli/`. [all]
- [x] T2 Packaging: pyproject with the console script, editable install through
  pixi, the store's default directory ignored by git.
  Verify: `pixi install && axis-of-travel-rnn --version`. [Non-Functional]
- [x] T3 Package modules the CLI imports: package init, `__main__`, environment
  builders, test package inits. Verify: `axis-of-travel-rnn env list`. [Commands]
- [x] T4 Store: `store.py` with resolution order, marker, layout, the manifest scan,
  and the counts behind `store inspect`. Verify: `axis-of-travel-rnn store init /tmp/s &&
  axis-of-travel-rnn --store /tmp/s store inspect`. [Data Model, Edge Cases]
- [x] T5 CLI package: root parser with `--store`, groups, the stub table, `store`,
  `env` and list commands, output helpers. Verify: `axis-of-travel-rnn --help`;
  `axis-of-travel-rnn data generate` exits 3. [Commands, Behavior]
- [x] T6 Tests: store logic; dispatch and exit codes; env list and inspect output;
  lists empty then registered; every stub exits 3. Verify: `pixi run test`. [Behavior]
- [x] T7 Docs: README setup and usage, reproduction commands, this list checked off. [all]
