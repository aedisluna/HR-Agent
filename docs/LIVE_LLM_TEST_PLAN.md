# Live LLM quality-test plan

Live model checks are intentionally separate from deterministic unit and API tests.
They will run only on demand or on a scheduled local job after the Ollama model is
available.

## Scope

- Analyze a fixed, anonymized vacancy corpus and validate the structured result.
- Generate CVs and form answers from confirmed candidate facts only.
- Run deterministic checks: schema validity, fact grounding, `evaluate_cv`, required
  platform sections, and refusal to invent unsupported skills or experience.
- Persist per-case duration, model version, pass/fail checks, and a redacted result
  summary so regressions can be compared between model or prompt versions.

## Acceptance criteria

A live case passes only when every deterministic invariant passes. Text similarity
or an LLM-only judge must not be the sole acceptance criterion.

## Execution model

- Keep test fixtures anonymized and independent from local candidate files.
- Run manually before releases and optionally as a nightly local job.
- Do not include live tests in the default `python -m pytest` command.
- Treat unavailable Ollama as an explicit skip, not a passing model-quality result.
