# Guides

How-to and operational guides for the `cssc-framework` repository, organized
around the **CSSC framework stages**. Within each stage, guides are grouped
under two cross-cutting themes where they apply: **Authenticity and Integrity**
and **Supply Chain Observability**.

- [Acquire](acquire/) — mirroring base images from Docker Hub into GHCR.
- [Catalog](catalog/) — promotion overrides and approvals for quarantined
  images.
- [Build](build/) — image tagging, annotations, and attestations for the demo
  app images.
- [Deploy](deploy/) — deploying the demo apps.
- [Run](run/) — running the applications.
- [Observability](observability/) — querying the supply-chain graph (artifact
  lineage, base images, tag history) through the `cssc-graph` CLI and the
  `graph-service` API. Cross-cutting across stages.
