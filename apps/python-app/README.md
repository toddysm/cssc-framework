# CSSC Dashboard

A scalable, Kubernetes-native demonstration app that visualizes the
[Containers Secure Supply Chain (CSSC) framework](https://aka.ms/cssc/framework)
**one stage at a time**, sourcing its data from this repository's GitHub
Container Registry (GHCR) packages and promotion tracking issues.

See the full design in
[docs/architecture/apps/cssc-dashboard.md](../../docs/architecture/apps/cssc-dashboard.md).

> Read-only demo. The dashboard never mutates packages or issues.

## Architecture

Three independently deployable, independently scalable microservices (FastAPI):

| Service | Role |
| ------- | ---- |
| [`packages-service`](services/packages-service/) | Lists GHCR container packages (the mirrored `quarantine/*` images) and their tags. Generic / reusable. |
| [`issues-service`](services/issues-service/) | Reads promotion tracking issues and parses the `blocking_cves` from their `cssc-metadata` block. Generic / reusable. |
| [`dashboard-web`](services/dashboard-web/) | Jinja2 + htmx UI and stage registry; a backend-for-frontend that aggregates the capability services. |

A shared library, [`libs/cssc_common`](libs/cssc_common/), holds the cached
GitHub HTTP client, the TTL cache, and the shared models.

```
Browser → dashboard-web → packages-service → GitHub Packages API
                        → issues-service   → GitHub Issues/Search API
```

The **Acquisition** stage is implemented first: per mirrored image, a table of
promotion issues (open and closed) with their blocking CVEs linked to a CVE
database. New stages are added as new providers in `dashboard-web`; new
capabilities as new microservices.

## Layout

```
apps/python-app/
  services/
    packages-service/   # FastAPI JSON API
    issues-service/     # FastAPI JSON API
    dashboard-web/      # FastAPI + Jinja2/htmx UI (BFF)
  libs/cssc_common/     # shared GitHub client, cache, models
  deploy/helm/          # umbrella chart -> 3 subcharts
  Makefile              # local dev on kind using the same Helm charts
```

## Local development (kind + Helm)

Local development uses a [kind](https://kind.sigs.k8s.io/) cluster and the **same
Helm charts** as any other environment — there is no separate `docker-compose`
path. Requires `docker`, `kind`, `kubectl`, and `helm`.

### Obtaining a GitHub token

The two capability services call the GitHub API and need a token in
`GITHUB_TOKEN` with:

- **`read:packages`** — to list GHCR container packages and their tags, and
- **issues read** — to read the promotion tracking issues.

Create a **classic** personal access token (most reliable for GHCR):

1. Go to **GitHub → Settings → Developer settings → Personal access tokens →
   Tokens (classic)** ([github.com/settings/tokens](https://github.com/settings/tokens)).
2. Click **Generate new token (classic)**, give it a name and an expiry.
3. Select these scopes:
   - `read:packages`
   - `repo` (or `public_repo` for a public repository) — grants issues read.
4. Click **Generate token** and copy it (it is shown only once).
5. Provide it to the project. The recommended way is a project-local `.env`
   file, which is gitignored and read automatically by the `Makefile`:

   ```bash
   cp .env.example .env
   # then edit .env and set GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
   ```

   Alternatively, export it in your shell:

   ```bash
   export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
   ```

> A fine-grained PAT also works for issues (Repository permissions →
> **Issues: Read-only**), but GHCR package listing is most reliably granted by
> the classic `read:packages` scope. Treat the token as a secret — never commit
> it.

```bash
# one-shot: create cluster, build images, load them, create the token secret,
# and install the umbrella chart
export GITHUB_TOKEN=ghp_xxx          # or put it in .env (see above)
make up

# browse the dashboard
make forward                          # http://localhost:8000

# tear everything down
make down
```

Run `make help` for the full target list (`venv`, `test`, `lint`, `build`,
`kind-up`, `load`, `secret`, `deploy`, `forward`, ...).

## Tests

```bash
make venv     # create .venv and install the library + all services
make test     # run unit tests for the library and every service
```

Tests are hermetic — GitHub and inter-service calls are mocked.

## Configuration

The capability services authenticate to GitHub with `GITHUB_TOKEN`
(`read:packages` + issues read), supplied via a Kubernetes `Secret`. The
dashboard tier needs no token — only the capability-service URLs and
`CVE_BASE_URL`. See each service's README for the full variable list.

## Supply chain

All deployment artifacts are sourced from this repository's GHCR package repo:

- **Base image** — the service images build `FROM ghcr.io/toddysm/golden/python:3.14-slim`
  (mirrored from Docker Hub into `quarantine/` and promoted through the
  vulnerability gate into `golden/`). Override `BASE_IMAGE` for local dev if the
  golden tag is unavailable, e.g. `make build BASE_IMAGE=python:3.14-slim`.
- **App images** — built and published to
  `ghcr.io/toddysm/apps/cssc-dashboard/<service>` by the `build / cssc-dashboard`
  workflow. Locally, `make build` tags images under the same names and `kind
  load`s them.
- **Helm charts** — published to `oci://ghcr.io/toddysm/charts` by the
  `build / cssc-dashboard-charts` workflow. Deploy from the package repo with
  `make deploy CHART=oci://ghcr.io/toddysm/charts/cssc-dashboard` (after
  `helm registry login ghcr.io`); the default `CHART` is the in-repo path for
  local development.
