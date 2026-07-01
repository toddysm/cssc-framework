# dashboard-web

CSSC Dashboard web tier: the stage registry, the Acquisition stage provider, and
the Jinja2/htmx UI. It is a backend-for-frontend that aggregates the
`packages-service` and `issues-service` capability services — it never calls
GitHub directly. See the
[CSSC Dashboard design](../../../../docs/architecture/apps/cssc-dashboard.md).

## Routes

| Method & path | Description |
| ------------- | ----------- |
| `GET /` | Full page: one section per registered stage. |
| `GET /stages/{id}/fragment` | htmx fragment for a stage (lazy-loaded). |
| `GET /healthz`, `GET /readyz` | Liveness / readiness. |

## Configuration

| Variable | Purpose |
| -------- | ------- |
| `PACKAGES_SERVICE_URL` | Base URL of packages-service (default `http://packages-service`). |
| `ISSUES_SERVICE_URL` | Base URL of issues-service (default `http://issues-service`). |
| `CVE_BASE_URL` | Base for CVE links; the CVE id is appended (default `https://nvd.nist.gov/vuln/detail/`). |
| `QUARANTINE_NAMESPACE` | Namespace treated as "mirrored" (default `quarantine`). |

No GitHub token is needed here — only the capability services authenticate to
GitHub.

## Adding a stage

1. Add a provider under `src/dashboard_web/stages/` exposing a `stage` (a
   `Stage`) and `get_data()`.
2. Register it in `build_registry()` in `app.py`.
3. Optionally add a `templates/stages/<id>.html` fragment (otherwise a generic
   view renders the raw data).

## Run locally

```bash
pip install -e ../../libs/cssc_common -e '.[test]'
PACKAGES_SERVICE_URL=http://localhost:8080 ISSUES_SERVICE_URL=http://localhost:8081 \
  uvicorn dashboard_web.app:app --port 8000
```

## Test

```bash
pip install -e ../../libs/cssc_common -e '.[test]'
pytest
```

## Build

```bash
# from apps/python-app/
docker build -f services/dashboard-web/Dockerfile -t dashboard-web .
```

## Vendored assets

`static/js/htmx.min.js` is [htmx](https://htmx.org/) 2.0.4, vendored so the app
needs no network access at runtime.
