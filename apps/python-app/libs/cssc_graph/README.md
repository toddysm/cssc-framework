# cssc-graph

File-backed supply-chain graph tooling for the CSSC framework.

**Phase 1** of the supply-chain graph
([design](../../../../docs/architecture/observability/supply-chain-graph.md),
epic #177): the data schema, identity rules, and a `validate` command. Later
phases add the LadybugDB indexer, query commands, and a graph service.

## Install

```bash
pip install -e ".[test]"
```

## CLI

```bash
# Validate every record under the data root against the JSON Schemas
cssc-graph validate supply-chain-graph

# Print the deterministic content id of a single record
cssc-graph id supply-chain-graph/examples/artifact-mirrored.yaml
```

`validate` exits non-zero on any error, so it fits pre-commit and CI.

For current indexing, query and integrity behavior, see the
[query guide](../../../../docs/guides/observability/querying-the-supply-chain-graph.md).
`index` emits unresolved-reference warnings by default;
`validate --strict-references` and `index --strict-references` reject missing
independent occurrence evidence. Deployment observations are available through
`deployments --ref`, and `tag-history --format json` includes explicit
observation-derived intervals and ambiguity.

## Concepts

- **Envelope** — the common wrapper on every record (`schemaVersion`, `kind`,
  `id`, `recordedAt`, `source`).
- **Occurrence identity** — fully qualified: `registry + repository + digest`.
- **Content id** — `sha256:` over the canonical semantic payload (everything
  except `id`, `recordedAt`, and `source`), so the same fact recorded twice is
  idempotent.
