# Documentation and evidence

The current `docs/` tree contains saved evaluation evidence under `evidence/`:

- `evidence/p0/` includes baseline evaluation data and a tier-0 test-run text artifact.
- `evidence/p12/` includes end-to-end evaluation data.

These files are retained records. They do not establish that the current working tree has been tested or that earlier results reproduce against this revision. The report generator in `scripts/generate_evaluation_report.py` expects `eval_results_45.json`, which is not present in the current working tree.
