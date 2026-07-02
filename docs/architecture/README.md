# Architecture

Design and architecture documentation for the `cssc-framework` repository,
organized around the **CSSC framework stages**. Within each stage, documents are
grouped under two cross-cutting themes where they apply: **Authenticity and
Integrity** and **Supply Chain Observability**.

## Stages

- [Acquire](acquire/) — mirroring upstream base images into a controlled
  namespace.
- [Catalog](catalog/) — scanning quarantined images and promoting the ones that
  pass a vulnerability policy into `golden/*`.
- [Build](build/) — building the demo apps into versioned, multi-arch images
  with supply-chain metadata.
- [Deploy](deploy/) — deploying the demo apps (currently the Helm charts under
  `apps/*/deploy`).
- [Run](run/) — the running applications, including the CSSC Dashboard.

## Cross-cutting

- [Cross-cutting](cross-cutting/) — design docs that span stages, such as
  CI-failure notifications.
