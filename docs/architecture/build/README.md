# Build — architecture

Design docs for the **Build** stage: building the demo apps on trusted bases and
attaching portable supply-chain metadata.

## Authenticity and Integrity

- [Build workflows](build-workflows.md) — how the demo applications are built
  into multi-arch OCI images, tagged with the semantic-version set, pinned to a
  digest-addressed base, and stamped with annotations, SBOM, and provenance.
  (The SBOM, provenance, and annotations also serve **Supply Chain
  Observability** — see the reference docs
  [image annotations](../../reference/image-annotations.md) and
  [image attestations](../../reference/image-attestations.md).)
