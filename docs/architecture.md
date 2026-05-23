# Agent Architecture

## Detection confidence policy

- **High (>=0.80)**: continue automatically
- **Medium (0.55-0.79)**: suggest mapping and request confirmation
- **Low (<0.55)**: block analysis and require manual confirmation

## Classification contract

Each candidate table classification must include:
- `table_type`
- `confidence`
- `key_columns`
- `rationale`
- `missing_requirements`

## Deterministic guardrails

- Analysis does not run unless required tables and ID columns are confirmed.
- LLM/heuristic output is validated before mapping is accepted.
- Invalid/missing columns fail fast with typed errors.

## Observability

- Prompt version tracked in classifier implementation.
- Redacted JSON logs avoid emitting PII fields.
- Per-run graph state persisted under `/tmp/lareview_runs`.
