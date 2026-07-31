# Acquire — architecture

Design docs for the **Acquire** stage: bringing upstream artifacts into a
controlled namespace before they are used.

## Authenticity and Integrity

- [Image mirror workflows](image-mirror-workflows.md) — how the Docker Hub →
  GHCR mirroring actions are structured, the tooling they use, and what they do
  and deliberately do not do.
- [Mirror history](mirror-history.md) — a durable, deletion-surviving record of
  the digests the mirror has already synchronized, so a promoted-and-deleted
  image is not re-mirrored (implemented, pending end-to-end validation).

## Supply Chain Observability

- [Acquisition provenance referrer](acquisition-provenance.md) — an OCI 1.1
  referrer attached to each mirrored image recording where it was acquired from
  and how (source registry, tag, digest, timestamp, workflow run).
