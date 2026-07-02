# Cross-cutting — architecture

Design docs that span multiple stages rather than belonging to a single one.

## Supply Chain Observability

- [CI failure notifications](ci-failure-notifications.md) — how a `workflow_run`
  monitor opens and closes per-workflow CI-failure tracking issues (and optional
  Slack alerts) across all monitored workflows when a run fails or recovers.
