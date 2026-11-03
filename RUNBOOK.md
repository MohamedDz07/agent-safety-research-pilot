# Runbook

1. From the repository root, create a Python 3.9+ virtual environment and run `python -m pip install -e '.[anthropic]'`.
2. Run `python -m unittest discover -s tests -v` and `agent-safety validate`.
3. Set `ANTHROPIC_API_KEY` in your local environment. Choose an exact model ID you can access and estimate API cost for up to 64 episodes with several turns each.
4. Run `agent-safety run --model YOUR_EXACT_MODEL_ID --output results/model-run-001`. To run an ablation subset, add `--variants baseline,policy` or another comma-separated subset.
5. Run `agent-safety score --input results/model-run-001`. Save `python -m pip freeze > results/model-run-001/environment.txt` for exact dependency provenance. Inspect `manifest.json`, `summary.json`, and every `episodes.jsonl` trace, especially incomplete episodes and cases where the model both completed the task and proposed a forbidden action.
6. Report the model ID, date, dataset hash, parameters, denominators, incomplete count, and selected failure traces. Label any claim as a synthetic pilot. Do not publish fixture metrics as model results.

Without an API key, `agent-safety demo --output results/fixture-check` verifies the local loop only. Use a new empty directory for each run. If an API call fails, the episode is marked incomplete; fix the cause and start a new run directory rather than mixing attempts.
