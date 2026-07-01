# issues-service

CSSC Dashboard capability service that reads promotion tracking issues and
parses the `blocking_cves` recorded in their `cssc-metadata` block. See the
[CSSC Dashboard design](../../../../docs/architecture/apps/cssc-dashboard.md).

## API

| Method & path | Description |
| ------------- | ----------- |
| `GET /issues?image=<repo>&tag=<tag>&state=all` | Promotion tracking issues: `[{number, title, url, state, outcome, image, tag, blocking_cves[]}]`. `image`, `tag`, `state` are optional filters. |
| `GET /healthz`, `GET /readyz` | Liveness / readiness. |

`outcome` is `pending` / `approved` / `denied`, derived from the issue labels.

## Configuration

| Variable | Purpose |
| -------- | ------- |
| `GITHUB_TOKEN` | Token with issues read access. |
| `GITHUB_OWNER`, `GITHUB_REPO` | Repository coordinates. |
| `GITHUB_API_URL` | Defaults to `https://api.github.com`. |
| `CACHE_TTL_SECONDS` | Response cache TTL (default `60`). |

## Run locally

```bash
pip install -e ../../libs/cssc_common -e '.[test]'
GITHUB_TOKEN=... GITHUB_OWNER=toddysm GITHUB_REPO=cssc-framework \
  uvicorn issues_service.app:app --port 8081
```

## Test

```bash
pip install -e ../../libs/cssc_common -e '.[test]'
pytest
```

## Build

```bash
# from apps/python-app/
docker build -f services/issues-service/Dockerfile -t issues-service .
```
