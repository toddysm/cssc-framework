# Acquisition provenance referrer

Every image mirrored from an external registry into `quarantine/<image>` carries
an **acquisition-provenance** OCI 1.1 Referrers-API artifact that records where
the image came from and how it was acquired. It is attached by the
[`attach-acquisition-provenance`](workflow-actions.md#attach-acquisition-provenance)
action from the [`_mirror-image.yml`](../../.github/workflows/_mirror-image.yml)
workflow, only on external → quarantine acquisitions (never on promotion), and
only when a copy actually happened.

The architecture and rationale are in
[docs/architecture/acquire/acquisition-provenance.md](../architecture/acquire/acquisition-provenance.md).

## Format

- **artifact type:** `application/vnd.in-toto+json`
- **predicate type:** `https://toddysm.com/acquisition-provenance/v0.1`

The referrer is attached to **both** the index/tag manifest and each
per-platform child manifest. The per-platform statements additionally record
`platformSourceDigest`.

## Predicate fields

| Field | Description |
| ----- | ----------- |
| `source.reference` | Full source reference (e.g. `docker.io/library/python:3.14-slim`). |
| `source.registry` | Source registry host (e.g. `docker.io`). |
| `source.repository` | Source repository (e.g. `library/python`). |
| `source.tag` | Source tag that was acquired. |
| `source.digest` | Source digest at acquisition time. |
| `destination.reference` | Destination reference in GHCR. |
| `destination.digest` | Acquired digest at the destination. |
| `acquiredAt` | RFC 3339 UTC acquisition timestamp. |
| `runUrl` | URL of the acquiring workflow run. |
| `actor` | Actor that triggered the run. |
| `workflow` | `{ name, runId, runAttempt }` of the acquiring run. |
| `copyMethod` | `crane` or `oras` (the latter when referrers were copied). |
| `copyReferrers` | Whether the mirror copied the image's referrers. |
| `sourceAuthenticated` | `true` when the mirror logged in to the source registry. |
| `platformSourceDigest` | Platform manifest digest (per-platform statements only). |

## Discovery annotations

Key fields are duplicated as annotations on the referrer manifest so they are
visible via `oras discover` without pulling the blob:

| Annotation | Example |
| ---------- | ------- |
| `in-toto.io/predicate-type` | `https://toddysm.com/acquisition-provenance/v0.1` |
| `org.opencontainers.image.title` | `acquisition-provenance.json` |
| `com.toddysm.acquisition.source` | `docker.io/library/python:3.14-slim` |
| `com.toddysm.acquisition.source-digest` | `sha256:<source-digest>` |
| `com.toddysm.acquisition.timestamp` | `2026-07-08T06:00:00Z` |
| `com.toddysm.acquisition.run-url` | `https://github.com/<owner>/cssc-framework/actions/runs/<id>` |

## Retrieve

```bash
# Index-level acquisition provenance (subject = the tag/index):
oras discover --format tree ghcr.io/<owner>/quarantine/python:3.14-slim

# Pull the in-toto statement (referrer digest from the tree above):
oras pull -o acq ghcr.io/<owner>/quarantine/python@<referrer-digest>

# Per-platform: resolve platform digests, then discover on each:
crane manifest ghcr.io/<owner>/quarantine/python:3.14-slim \
  | jq -r '.manifests[]
      | select((.platform.os // "") != "" and (.platform.os // "") != "unknown")
      | "\(.platform.os)/\(.platform.architecture)\t\(.digest)"'
oras discover --format tree ghcr.io/<owner>/quarantine/python@<platform-digest>
```
