# Observability — architecture

Design docs for the **Supply Chain Observability** theme that need their own
home rather than living inside a single stage.

## Supply-chain graph

- [Supply-chain graph: file-backed indexing](supply-chain-graph.md) — how
  version-controlled data files (written by the acquire, catalog, build, and
  deploy workflows and by hand) are indexed into a local, rebuildable graph
  (LadybugDB) and queried through a CLI and a Kubernetes service.

Requirements: [#168](https://github.com/toddysm/cssc-framework/issues/168).
Supersedes the storage-engine choice in [#145](https://github.com/toddysm/cssc-framework/issues/145)
(Kùzu is archived; LadybugDB is its maintained successor).
