# Querying the supply-chain graph

The supply-chain graph turns the version-controlled event records under
[`supply-chain-graph/`](../../../supply-chain-graph) into a queryable graph so you
can answer questions such as *"where did this image come from?"*, *"what is this
image built on?"*, and *"what did this tag point to last month?"*.

There are two ways to ask those questions, and they share the **same query
layer** (`cssc_graph.queries`):

- The **`cssc-graph` CLI** — local, offline, no service required. Best for
  authoring, CI validation, scripting, and ad-hoc investigation.
- The **`graph-service` HTTP API** — the in-cluster read API that also backs the
  dashboard's *Supply chain graph* view. Best for shared, always-on access.

Because both call the same functions, a CLI command and its HTTP endpoint return
the same answer. Start with the CLI — it is the fastest way to see the whole
model — then move to the service when you want it running for others.

For the design and data model, see
[Supply-chain graph: file-backed indexing](../../architecture/observability/supply-chain-graph.md).
The functional requirements and the list of questions this guide answers come
from [#168](https://github.com/toddysm/cssc-framework/issues/168).

> **Scope.** Phases 1–6 cover artifact identity, the acquire → catalog → build →
> deploy path, base-image lineage, tag history, annotations, and artifact
> details. Package/file inventory, CVEs and vulnerability-introduction points,
> and signer/verification queries are **deferred to Phase 7** and are called out
> where they apply.

---

## The model in one minute

- The **source of truth** is the folder of records under `supply-chain-graph/`
  (`events/` written by the workflows, `examples/` fixtures, and `schema/`). It
  is version-controlled and human-editable.
- The **graph database** is *derived state*: `cssc-graph index` reads the records
  and materializes a LadybugDB directory (default `.graph`). It is rebuildable
  and disposable — delete it and re-index anytime. Re-indexing unchanged files is
  idempotent.
- An **artifact** is content identity (a digest). An **occurrence** is that digest
  *in a specific `registry/repository`*. The same digest legitimately occurs in
  many repositories and stages, so occurrences — not digests — are the nodes that
  edges connect: `MIRRORED_FROM`, `PROMOTED_FROM`, `BUILT_FROM`, `POINTED_TO`
  (tags, kept as history), and `RUNS` (deployments).

The examples below use the fixtures in `supply-chain-graph/examples/`, so you can
run every command verbatim.

---

## Experience 1 — the `cssc-graph` CLI

### Install

The CLI ships with the `cssc_graph` library. From `apps/python-app`:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e './libs/cssc_graph[test]'
cssc-graph --help
```

(`make venv` from `apps/python-app` also installs it into `.venv`.)

### Build the graph (validate, then index)

Everything below queries a database directory, so build one first. `index`
validates before it writes, so invalid records stop the build with actionable
diagnostics instead of a half-built graph.

```bash
cd /path/to/cssc-framework

# Optional: check records without building anything.
cssc-graph validate supply-chain-graph

# Build (or rebuild) the graph. -d is the database directory; --rebuild wipes it.
cssc-graph index supply-chain-graph -d /tmp/demo-db --rebuild
```

```text
Indexed 7 record(s) into /tmp/demo-db.
  ArtifactBuilt: 1
  ArtifactDeployed: 1
  ArtifactMirrored: 1
  ArtifactObserved: 1
  ArtifactPromoted: 2
  TagObserved: 1
```

> `-d/--database` is just the path to the derived DB directory (default `.graph`,
> git-ignored). The examples use `-d /tmp/demo-db`; set it once as `DB=/tmp/demo-db`
> to shorten the commands. Every query command accepts `--format text|json`.

### Answering the common questions

Each question below is one of the required query outcomes from the requirements.

#### 1. Given a digest — every occurrence and the full path

`path --digest` seeds **all** occurrences of the digest and walks the supply chain
in both directions.

```bash
DB=/tmp/demo-db
D=sha256:$(printf '2%.0s' {1..64})       # a digest from the examples
cssc-graph path --digest "$D" -d "$DB"
```

```text
5 node(s), 3 edge(s):
  ghcr.io/toddysm/quarantine/python      --MIRRORED_FROM--> docker.io/library/python (3.14-slim)
  second.registry.io/quarantine/python   --PROMOTED_FROM--> first.registry.io/quarantine/python (3.14-slim)
  ghcr.io/toddysm/golden/python          --PROMOTED_FROM--> ghcr.io/toddysm/quarantine/python (3.14-slim)
```

Every node in that result is an occurrence of the digest. To list just the
occurrences (the service's `GET /artifacts/resolve?digest=…` does the same):

```bash
cssc-graph cypher -d "$DB" 'MATCH (o:Occurrence) WHERE o.digest = "'"$D"'" RETURN o.ref AS ref'
```

#### 2. Given a repository and tag — current target and full history

`tag-history` returns every digest a tag pointed to, in chronological order (tags
are stored as append-only observations, never a mutable edge, so history is
preserved). `show` resolves the current/indexed target.

```bash
cssc-graph tag-history --repo ghcr.io/toddysm/golden/python --tag 3.14-slim -d "$DB"
cssc-graph show --ref ghcr.io/toddysm/golden/python:3.14-slim -d "$DB"
```

```text
2026-08-09T13:10:05Z  sha256:2222…2222  https://github.com/toddysm/cssc-framework/actions/runs/123450002
1 observation(s).

occurrence: ghcr.io/toddysm/golden/python@sha256:2222…2222
  tag: 3.14-slim @ 2026-08-09T13:10:05Z
```

#### 3. Given a built image — direct and transitive base images

`bases` follows `BUILT_FROM` up the chain (and each base's own path is reachable
by re-running `path`/`bases` on it).

```bash
cssc-graph bases --ref ghcr.io/toddysm/apps/cssc-dashboard/issues-service -d "$DB"
```

```text
2 node(s), 1 edge(s):
  ghcr.io/toddysm/apps/cssc-dashboard/issues-service --BUILT_FROM--> ghcr.io/toddysm/golden/python (3.14-slim)
```

#### 4. Downstream — every image built from a base

`derived` is `bases` in reverse: given a base, find everything transitively built
on it (a downstream-impact query).

```bash
cssc-graph derived --base ghcr.io/toddysm/golden/python -d "$DB"
```

#### 5. Find artifacts by annotation, type, or repository

```bash
cssc-graph find --annotation com.toddysm.image.base.tag=3.14-slim -d "$DB"
cssc-graph find --type application/vnd.oci.image.index.v1+json -d "$DB"
cssc-graph find --ref ghcr.io/toddysm/golden/python -d "$DB"
```

```text
ghcr.io/toddysm/golden/python  sha256:1111…1111
1 match(es).
```

> Finding by **package, file, CVE, signer, or verification state** is Phase 7 and
> not yet available.

#### 6. Inspect one artifact

`show` needs a *specific* occurrence — `registry/repository@digest` or
`registry/repository:tag` — and returns its occurrence, artifact metadata,
annotations, tags, and nearby path.

```bash
cssc-graph show --ref ghcr.io/toddysm/golden/python:3.14-slim -d "$DB" --format json
```

> `show` currently returns the occurrence, annotations, tags, and path. **Layers,
> packages, files, CVEs, and signatures/signers** are Phase 7.

#### 7. Where an image is deployed

Deployments are recorded as `ArtifactDeployed` (a `Deployment`—`RUNS`→`Occurrence`
edge). There is no dedicated verb yet, so query it with `cypher`:

```bash
cssc-graph cypher -d "$DB" \
  MATCH '(dep:Deployment)-[:RUNS]->(o:Occurrence)' \
  RETURN dep.key AS deployment, o.ref AS image, o.digest AS digest
```

```text
deployment=kind-cssc/default  image=ghcr.io/toddysm/apps/cssc-dashboard/issues-service  digest=sha256:4444…4444
```

#### 8. Export a subgraph for visualization

`export` emits a bounded subgraph as Cytoscape JSON, Mermaid, or plain JSON.

```bash
cssc-graph export --ref ghcr.io/toddysm/quarantine/python --format mermaid -o chain.mmd -d "$DB"
```

#### 9. Escape hatch — read-only Cypher

Anything the verbs do not cover is reachable with `cypher`. It is read-only
(write clauses are rejected) and multi-word queries need no quoting.

```bash
cssc-graph cypher -d "$DB" MATCH '(o:Occurrence)' RETURN count'(o)' AS n
```

---

## Experience 2 — the `graph-service` HTTP API

`graph-service` is a FastAPI service that owns a single LadybugDB writer, rebuilds
the graph from the committed records on startup, and gates readiness on a
successful index. It exposes the same journeys as the CLI over HTTP and backs the
dashboard's graph view.

### Run it

**Locally** (points the service at the in-repo example data):

```bash
cd /path/to/cssc-framework
DATA_ROOT=supply-chain-graph DATABASE_PATH=/tmp/graph-db REBUILD_ON_STARTUP=true \
  python -m uvicorn graph_service.app:app --port 8004
```

**In a cluster** via the umbrella chart (see the deploy guides). The subchart
runs one replica, indexes on startup, and can pull the committed data with an
optional git-sync init container (`graph-service.gitSync.enabled=true`, off by
default so a first deploy is green before the `supply-chain-graph-data` branch
exists).

Check readiness — it reports how many records were indexed:

```bash
curl -s localhost:8004/readyz | jq
# { "status": "ready", "records": 7, "byKind": { "ArtifactPromoted": 2, … }, "root": "supply-chain-graph" }
```

Rebuild on demand (e.g. after new records land):

```bash
curl -s -X POST localhost:8004/index/rebuild | jq
```

### The same questions, as endpoints

Refs and digests contain `/`, `@`, and `:`, so they are passed as query
parameters. `depth` is clamped to the service's `MAX_DEPTH`.

| Question | CLI | Endpoint |
|---|---|---|
| Occurrences of a digest | `path --digest` / `find` | `GET /artifacts/resolve?digest=…`, `GET /artifacts/path?digest=…` |
| Full supply-chain path | `path` | `GET /artifacts/path?ref=…` (or `?digest=…`) |
| Current tag target | `show --ref repo:tag` | `GET /artifacts/show?ref=repo:tag` |
| Tag history | `tag-history` | `GET /repositories/tags/history?ref=…&tag=…` |
| Direct + transitive bases | `bases` | `GET /artifacts/bases?ref=…` |
| Downstream derived images | `derived` | `GET /artifacts/derived?base=…` |
| Find by annotation/type/repo | `find` | `GET /search?annotation=…` / `?type=…` / `?ref=…` |
| Inspect one artifact | `show` | `GET /artifacts/show?ref=…` |
| Bounded subgraph for viz | `export` | `GET /graph/neighborhood?ref=…&format=json\|cytoscape\|mermaid` |
| Health / readiness | — | `GET /healthz`, `GET /readyz` |
| Rebuild the index | `index --rebuild` | `POST /index/rebuild` |

Examples:

```bash
D=sha256:$(printf '2%.0s' {1..64})

# 1. Given a digest: occurrences + path
curl -s "localhost:8004/artifacts/resolve?digest=$D" | jq
curl -s "localhost:8004/artifacts/path?digest=$D" | jq

# 2. Repo + tag: current target + history
curl -s "localhost:8004/artifacts/show?ref=ghcr.io/toddysm/golden/python:3.14-slim" | jq
curl -s "localhost:8004/repositories/tags/history?ref=ghcr.io/toddysm/golden/python&tag=3.14-slim" | jq

# 3/4. Bases and derived
curl -s "localhost:8004/artifacts/bases?ref=ghcr.io/toddysm/apps/cssc-dashboard/issues-service" | jq
curl -s "localhost:8004/artifacts/derived?base=ghcr.io/toddysm/golden/python" | jq

# 5. Find; 8. neighborhood for visualization
curl -s "localhost:8004/search?annotation=com.toddysm.image.base.tag=3.14-slim" | jq
curl -s "localhost:8004/graph/neighborhood?ref=ghcr.io/toddysm/quarantine/python&format=mermaid"
```

> Endpoints for CVE impact / introduction points and package/file lookups are
> Phase 7 and not present yet.

### The dashboard view

The dashboard's **Supply chain graph** section (served by `dashboard-web`, which
calls `graph-service`) shows the index summary and an explore box. Enter a
reference — e.g. `ghcr.io/toddysm/quarantine/python` — to render its bounded
neighborhood (nodes and edges) using `GET /graph/neighborhood`. Point
`dashboard-web` at the service with `GRAPH_SERVICE_URL` (default
`http://graph-service`).

---

## How the two relate

The CLI and the service are two front ends over one query layer
(`cssc_graph.queries`): `cssc-graph path` and `GET /artifacts/path` run the same
code, so answers never diverge. Use the CLI for local authoring, CI checks
(`validate`, `id`), and scripting; run the service when you want the graph
available to the dashboard and to others. Both treat the database as disposable,
derived state and rebuild it from the version-controlled records.

## Not covered yet (Phase 7)

The requirements also call for package/file inventory, CVE association and
evidence-backed introduction points, and signer/verification queries. These
depend on SBOM and scan ingestion and are deferred to Phase 7
([#176](https://github.com/toddysm/cssc-framework/issues/176)). Until then,
`find` covers annotation/type/repository, and `show` covers occurrence metadata,
annotations, tags, and path.
