# Project scripts

Scripts in this directory serve separate setup, demo, hardware-check, and report-generation purposes.

- `demo_phase1.py` runs a Phase 1 system demonstration using the agent loop, tool registry, and state database. It may create or update local runtime state.
- `gpu_smoke_test.py` probes Python, PyTorch, CUDA, and GPU memory. It requires optional hardware-specific dependencies and a compatible GPU for a full result.
- `generate_evaluation_report.py` reads `eval_results_45.json` and writes `REAL_LIFE_EVALUATION_REPORT.md`. The expected input JSON is not in the current working tree, so the report command cannot run from this checkout as-is.
- `setup_agent_account.ps1` creates a Windows local account and changes filesystem ACLs unless run with `-DryRun`; a real run requires administrator privileges. Review the script before using it.

No script in this folder was executed for this documentation update.
