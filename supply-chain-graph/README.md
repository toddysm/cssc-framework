# supply-chain-graph — data files

Version-controlled data for the CSSC **supply-chain graph**. These files are the
system of record; the graph database (LadybugDB) is a rebuildable index over
them.

Design: [docs/architecture/observability/supply-chain-graph.md](../docs/architecture/observability/supply-chain-graph.md).

## Layout

```text
supply-chain-graph/
  sources.yaml     # curated: remote roots the indexer may crawl
  schema/          # JSON Schemas for the envelope and each record kind
  events/          # producer-written, append-only, immutable event records
    <yyyy>/<mm>/<dd>/<ts>-<stage>-<kind>-<hash>.yaml
  examples/        # one illustrative, valid record per kind (reference only)
```

## Rules

- **Producers only ever create new files.** Every run writes a new, uniquely
  named file under `events/`; existing files are never edited or deleted. This
  makes ingestion idempotent and conflict-free.
- **Fully-qualified identity.** An occurrence is keyed by
  `registry + repository + digest`; references are written
  `registry/repository@sha256:…`, never a bare repository — so cross-registry
  promotion chains stay distinct and linked.
- **Evidence, not secrets.** Records carry only digests, refs, tags, timestamps,
  and public run/issue URLs. Never commit tokens or signing material.

## Validate

```bash
cssc-graph validate supply-chain-graph
```

The `validate` command (see `apps/python-app/libs/cssc_graph`) checks every
record against the schemas in `schema/` and exits non-zero on any error, so it
fits pre-commit and CI.
