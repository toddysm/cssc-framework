# cssc_common

Shared building blocks for the CSSC Dashboard microservices. See the
[CSSC Dashboard design](../../../../docs/architecture/run/cssc-dashboard.md).

## What's here

| Module | Purpose |
| ------ | ------- |
| `github.py` | `GitHubClient` — a small, cached `httpx` wrapper around the GitHub REST API (auth, API-version header, `Link` pagination). |
| `cache.py` | `TTLCache` — a tiny thread-safe time-to-live cache. |
| `models.py` | Shared Pydantic models: `Tag`, `MirroredImage`, `PromotionIssue`, `Cve`. |
| `config.py` | `github_settings()` — environment-driven `GitHubSettings`. |

## Install

```bash
pip install -e .
```

## Test

```bash
pip install -e '.[test]'
pytest
```
