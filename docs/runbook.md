# Operations Runbook

## Failed detection

1. Inspect `/api/sessions/{session_id}/detect` response errors.
2. Use `/api/sessions/{session_id}/confirm` to manually provide mapping.
3. Re-run analysis.

## Model drift tuning

1. Review persisted run state and confidence trends.
2. Update classifier prompt/version and feature hints.
3. Re-run fixture regression tests.

## Manual override

- Use confirm endpoint to bind table IDs and key columns directly.
- Keep duplicate policy explicit (`exact`, `normalized`, `substring`).

## Suggested metrics

- detection accuracy (manual override rate)
- analysis latency (p95 job completion)
- failure rate (failed jobs / total jobs)
- confidence distribution by table type
