# packages-service

CSSC Dashboard capability service that lists GHCR container packages and their
tags via the GitHub Packages API. See the
[CSSC Dashboard design](../../../../docs/architecture/run/cssc-dashboard.md).

## API

| Method & path | Description |
| ------------- | ----------- |
| `GET /packages?namespace=quarantine` | Container packages under a namespace: `[{name, visibility, updated_at, tag_count}]`. |
| `GET /packages/{name}/tags` | Tags of a package: `[{tag, digest, updated_at}]`. |
| `GET /healthz`, `GET /readyz` | Liveness / readiness. |

## Configuration

| Variable | Purpose |
| -------- | ------- |
| `GITHUB_TOKEN` | Token with `read:packages`. |
| `GITHUB_OWNER` | Package owner (user/org). |
| `GITHUB_OWNER_TYPE` | `user` (default) or `org`; selects the `/users/{owner}` vs `/orgs/{owner}` Packages API root. |
| `GITHUB_API_URL` | Defaults to `https://api.github.com`. |
| `CACHE_TTL_SECONDS` | Response cache TTL (default `60`). |

## Run locally

```bash
pip install -e ../../libs/cssc_common -e '.[test]'
GITHUB_TOKEN=... GITHUB_OWNER=toddysm uvicorn packages_service.app:app --port 8080
```

## Test

```bash
pip install -e ../../libs/cssc_common -e '.[test]'
pytest
```

## Build

```bash
# from apps/python-app/
docker build -f services/packages-service/Dockerfile -t packages-service .
```
