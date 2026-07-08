# Acquisition provenance referrer

> **Status: implemented.** Tracking issue: #140. See the
> [attach-acquisition-provenance action](../../../.github/actions/attach-acquisition-provenance/action.yml)
> and [`_mirror-image.yml`](../../../.github/workflows/_mirror-image.yml).

When an image is **acquired** — mirrored from an external registry into the
owner-controlled `quarantine/<image>` namespace — the framework has no
first-party record of *where the image came from* or *how it was pulled*. Once
an image sits in quarantine, the acquisition context (source registry, tag,
digest, timestamp, workflow run) is lost.

This design adds a first-party **OCI 1.1 Referrers-API artifact** that records
the acquisition details and travels with the mirrored image in GHCR, so the
question "where did this image come from, and when did we pull it?" can be
answered from the artifact itself — portably and registry-natively.

## Goals

- Record the source of every acquired image (registry, repository, tag, digest).
- Record how and when it was acquired (timestamp, workflow run, copy method).
- Store the record as a standards-based, discoverable OCI 1.1 referrer that
  survives copies and is readable with common tooling (`oras discover`).
- Keep the acquisition (mirror) action small and single-purpose.

## Non-goals

- **Promotion provenance.** The `mirror-image` action also backs the
  quarantine → golden promotion (a mirror with `force=true`). Acquisition
  provenance is recorded **only** on the external → quarantine acquisition, not
  on promotion. Promotion provenance, if wanted, is a separate future design.
- **Signing / verification.** The referrer is not signed here, and existing
  upstream referrers are not re-verified (unchanged from today's mirror scope).
- **Retention / dedup of historical referrers.** See
  [Idempotency and history](#idempotency-and-history).

## Artifact format

The referrer is an **in-toto Statement**, consistent with the SBOM and
provenance referrers this repo already publishes (see
[image attestations](../../reference/image-attestations.md)):

- **artifact type:** `application/vnd.in-toto+json`
- **predicate type:** `https://toddysm.com/acquisition-provenance/v0.1`

Using in-toto keeps the acquisition record in the same shape as the other
attestations and makes it discoverable with the same tooling.

### Predicate schema

The in-toto Statement's `subject` names the acquired manifest (see
[Subjects](#subjects)); the `predicate` carries the acquisition details:

```jsonc
{
  "_type": "https://in-toto.io/Statement/v1",
  "predicateType": "https://toddysm.com/acquisition-provenance/v0.1",
  "subject": [
    { "name": "ghcr.io/<owner>/quarantine/python",
      "digest": { "sha256": "<acquired-manifest-digest>" } }
  ],
  "predicate": {
    // --- core (always present) ---
    "source": {
      "reference": "docker.io/library/python:3.14-slim",
      "registry": "docker.io",
      "repository": "library/python",
      "tag": "3.14-slim",
      "digest": "sha256:<source-index-digest>"
    },
    "destination": {
      "reference": "ghcr.io/<owner>/quarantine/python:3.14-slim",
      "digest": "sha256:<acquired-manifest-digest>"
    },
    "acquiredAt": "2026-07-08T06:00:00Z",   // RFC 3339 UTC
    "runUrl": "https://github.com/<owner>/cssc-framework/actions/runs/<id>",

    // --- optional (recorded per design decision) ---
    "actor": "<github.actor>",
    "workflow": {
      "name": "mirror / quarantine/python",
      "runId": "<github.run_id>",
      "runAttempt": "<github.run_attempt>"
    },
    "copyMethod": "crane",                  // "crane" | "oras"
    "copyReferrers": false,                  // whether referrers were copied
    "sourceAuthenticated": false,            // true when a source login was used
    "platformSourceDigest": "sha256:<...>"   // only in per-platform statements
  }
}
```

Notes:

- `platformSourceDigest` appears **only** in the per-platform statements; it
  records the specific platform manifest digest that statement describes.
- `sourceAuthenticated` is `true` when the mirror logged in to a source registry
  (e.g. `dhi.io`) rather than pulling anonymously. It does **not** record any
  credential.

### Discovery annotations

Key fields are duplicated as annotations on the referrer manifest so
`oras discover` and registry UIs can surface them without pulling the blob:

| Annotation | Example |
| ---------- | ------- |
| `in-toto.io/predicate-type` | `https://toddysm.com/acquisition-provenance/v0.1` |
| `org.opencontainers.image.title` | `acquisition-provenance.json` |
| `com.toddysm.acquisition.source` | `docker.io/library/python:3.14-slim` |
| `com.toddysm.acquisition.source-digest` | `sha256:<source-digest>` |
| `com.toddysm.acquisition.timestamp` | `2026-07-08T06:00:00Z` |
| `com.toddysm.acquisition.run-url` | `https://github.com/.../runs/<id>` |

The `com.toddysm.*` namespace and dashed keys match the existing image
annotation convention (see [image annotations](../../reference/image-annotations.md)).

## Subjects

The referrer is attached to **both** the tag/index manifest **and** each
per-platform child manifest of the acquired image:

- **Index / tag** — one statement describing the acquired image as a whole; its
  subject digest is the index digest.
- **Per-platform** — one statement per child manifest; its subject digest is the
  platform manifest digest, and it additionally carries `platformSourceDigest`.

Because `crane`/`oras` preserve digests during the copy, the acquired
(destination) digests equal the source digests, so every statement's subject
link is valid against the copied image. Attaching at both levels mirrors how the
existing SBOM/provenance referrers attach per-platform while also giving a
single index-level record for the whole image.

## When it runs

The referrer is created **only when a copy actually happened** — i.e. when the
`mirror-image` action reports `copied == true`. When the destination is already
up to date, no new referrer is written. This ties each acquisition referrer to a
distinct acquired digest and avoids churn on unchanged images.

## Where it lives

A new single-purpose composite action **`attach-acquisition-provenance`** under
[`.github/actions/`](../../../.github/actions/) builds the predicate and
attaches it with `oras attach`. It is orchestrated by the reusable
[`_mirror-image.yml`](../../../.github/workflows/_mirror-image.yml) workflow —
**not** by the promotion workflows — which is what scopes the feature to
external acquisition only.

```text
.github/
├── actions/
│   ├── mirror-image/                    # copies the image (unchanged)
│   └── attach-acquisition-provenance/   # NEW — attaches the referrer
└── workflows/
    └── _mirror-image.yml                # calls mirror-image, then (on copied) the new action
```

### Reusable-workflow wiring

`_mirror-image.yml` gains one input:

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `record_acquisition_provenance` | no | `true` | Attach an acquisition-provenance referrer to the mirrored image after a successful copy. |

New/changed steps in the `mirror` job:

1. **Set up oras** — the condition widens from `copy_referrers == true` to
   `copy_referrers == true || record_acquisition_provenance == true`, because
   `oras attach` needs the CLI.
2. **Mirror image** (`mirror-image`) — unchanged; still outputs `copied`,
   `digest`, `previous-digest`.
3. **Attach acquisition provenance** (`attach-acquisition-provenance`) — runs
   `if: record_acquisition_provenance == true && steps.mirror.outputs.copied == 'true'`.
   Receives the source ref/digest, destination ref/digest, and the copy context.

The action:

- resolves the acquired index digest and enumerates per-platform child digests
  (via `crane manifest` / `oras manifest fetch`),
- writes one predicate JSON per subject,
- attaches each with
  `oras attach --artifact-type application/vnd.in-toto+json
  --annotation in-toto.io/predicate-type=https://toddysm.com/acquisition-provenance/v0.1
  --annotation ... --disable-path-validation <subject-ref> <file>:application/vnd.in-toto+json`.

`--disable-path-validation` is required due to a known `oras attach` regression
with absolute temp-file paths (see #139). GHCR auth is already established by the
existing "Log in to GHCR" step, so no new secrets are needed.

## Idempotency and history

`oras attach` **adds** a referrer; it does not replace existing ones. Because the
action only runs when `copied == true`, each acquisition changes the destination
digest (for a non-referrer copy the digests differed by definition), so each new
acquisition referrer attaches to a **new** subject digest. Re-pulling the same
unchanged tag does not create duplicates. Multiple acquisition referrers on the
*same* subject digest are therefore not expected in normal operation; pruning of
historical referrers is out of scope for this design.

## Retrieval

```bash
# Index-level acquisition provenance (subject = the tag/index):
oras discover --format tree ghcr.io/<owner>/quarantine/python:3.14-slim

# Pull the in-toto statement (referrer digest from the tree above):
oras pull -o acq ghcr.io/<owner>/quarantine/python@<referrer-digest>

# Per-platform: resolve platform digests, then discover on each:
crane manifest ghcr.io/<owner>/quarantine/python:3.14-slim \
  | jq -r '.manifests[] | select(.platform.os != "unknown")
      | "\(.platform.os)/\(.platform.architecture)\t\(.digest)"'
oras discover --format tree ghcr.io/<owner>/quarantine/python@<platform-digest>
```

## Open questions

- Should the index-level statement enumerate all platform subject digests in its
  predicate (a manifest of manifests), or is the per-platform statement set
  sufficient? (Leaning: per-platform set is sufficient.)
- Versioning policy for the `v0.1` predicate type as fields evolve.
