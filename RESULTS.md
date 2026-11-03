# Results status

**Model experiments: not run.** No API key was supplied for this delivery. There are no observed model safety rates, no model comparisons, and no research conclusion.

The automated tests and deterministic fixture verify that the dataset loads, the tool loop records proposals and decisions, the policy blocks unauthorized action/target pairs, the monitor ablation flags the scripted injections, and the scorer computes case-level metrics and Wilson intervals. Fixture output is synthetic software verification and must remain separate from any eventual model results.

When real experiments are run, place their generated records under `results/` locally and add an analysis that cites the exact manifest and dataset hash. Review the raw traces before publishing aggregate numbers.
