# Workflow actions and terminology

This repository's GitHub Actions are built from small, single-purpose
**composite actions** under [`.github/actions/`](../../.github/actions/). The
reusable workflows (`_*.yml`) orchestrate these actions; the per-image callers
(`mirror-*.yml`, `scan-*.yml`) only supply configuration.

This document is the canonical reference for:

1. [Terminology](#terminology) — the standard verbs and nouns used in action
   names, step names, inputs, and docs.
2. [Action catalogue](#action-catalogue) — what each composite action does and
   its inputs/outputs.
3. [How the actions compose](#how-the-actions-compose) — how the reusable
   workflows wire the actions together.

## Terminology

Use these terms consistently across workflows, actions, commit messages, and
docs. The left column is the canonical term; the right column lists the older
phrasings it replaces.

| Canonical term | Meaning | Replaces |
| -------------- | ------- | -------- |
| **registry-login** | Authenticate the local clients to a registry. | "Log in to GHCR", "Log in to source registry" |
| **enumerate-tags** | List the tags in a repository. | "Enumerate quarantine tags", "list tags" |
| **mirror-image** | Idempotently copy one image between registries (digest-compare + copy). | "compare digests and copy", "crane copy" |
| **promote-image** | Copy a passing image from quarantine into golden/base. Implemented as **mirror-image** with `force: true`. | "promote", "promote passing images" |
| **copy-referrers** | Copy an image together with its OCI referrers (`oras cp -r` + per-platform children). Folded into **mirror-image** via `copy-referrers: true`. | "copy_referrers", "copy with referrers" |
| **scan-image** | Scan one image filesystem with `trivy image`. | "scan images with Trivy" |
| **scan-sbom** | Scan one image's per-platform SBOM attestations with `trivy sbom`. | "scan platform SBOMs" |
| **evaluate-findings** | Apply the severity threshold + CVE exceptions to produce a gate decision. | "gate on scan findings" |
| **attach-scan-report** | Attach the OCI scan-report referrer to a promoted image. | "attach scan-report attestation" |
| **delete-image** | Delete one tag from a GHCR repository via the Packages API. | "delete promoted tags from quarantine" |

Standard nouns:

- **image** — one tagged artifact (`repository:tag`).
- **repository** — an untagged repository (`registry/owner/path`).
- **tag**, **digest**, **referrers** — as in the OCI spec.
- **quarantine** — the untrusted landing repository (`quarantine/<image>`).
- **golden** / **base** — promotion targets for clean images (`golden/<image>`,
  `base/hardened/<image>`).
- **decision** — the gate outcome: `promote`, `dryrun`, `blocked`, or
  `blocked-missing-sbom`.

## Action catalogue

All actions are composite actions invoked with `uses: ./.github/actions/<name>`.
They assume the relevant CLIs (`crane`, `oras`, `trivy`, `jq`, `gh`) are already
installed by the calling job, and that the repository has been checked out (with
`actions/checkout`) so the local action files are on disk.

### registry-login

Log in to a container registry with `crane` (and optionally `oras`).

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `registry` | yes | — | Registry hostname (e.g. `ghcr.io`, `dhi.io`). |
| `username` | yes | — | Registry username. |
| `password` | yes | — | Password/token (passed via stdin). |
| `with-oras` | no | `false` | Also log in `oras`. |

### enumerate-tags

List the tags in a repository as a JSON array for matrix fan-out.

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `repository` | yes | — | Repository to enumerate, without tag. |
| `exclude-referrer-tags` | no | `false` | Drop OCI referrer fallback tags (`sha256-*`). |

Outputs: `tags-json` (JSON array), `has-tags` (`true`/`false`).

### mirror-image

Idempotently copy one image (optionally with its referrers) between registries.
Backs both the upstream → quarantine mirror and the quarantine → golden/base
promotion (promotion is a mirror with `force: true`).

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `source-image` | yes | — | Source image without tag. |
| `source-tag` | yes | — | Source tag. |
| `dest-image` | yes | — | Destination image without tag. |
| `dest-tag` | yes | — | Destination tag. |
| `force` | no | `false` | Copy even when digests match. |
| `copy-referrers` | no | `false` | Use `oras cp -r` to carry referrers (SBOM/provenance/VEX/signatures). |

Outputs: `copied`, `digest`, `previous-digest`, `referrers-note`.

### scan-image

Scan one image filesystem with `trivy image`.

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `image-ref` | yes | — | Image reference to scan (`repo:tag`). |
| `severities` | yes | — | Comma-separated severities (e.g. `HIGH,CRITICAL`). |
| `output-dir` | yes | — | Directory for `report.json` and `blocking-ids.txt`. |

Outputs: `report-path`, `blocking-ids-path`.

### scan-sbom

Scan one image's per-platform SBOM attestations with `trivy sbom`.

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `image-ref` | yes | — | Image reference to scan (`repo:tag`). |
| `repository` | yes | — | Repository the image lives in (for referrer fetch). |
| `severities` | yes | — | Comma-separated severities. |
| `sbom-predicate-type` | yes | — | in-toto predicate type of the SBOM to scan. |
| `exceptions-file` | yes | — | Sorted file of excepted CVE IDs (per-platform breakdown only). |
| `output-dir` | yes | — | Directory for SBOMs, reports, and the blocking-ids list. |

Outputs: `blocking-ids-path`, `missing-sbom-count`, `platform-count`,
`platform-detail-path`.

### evaluate-findings

Apply the gate (threshold + exceptions) to one image's findings.

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `blocking-ids-file` | yes | — | Vulnerability IDs the scanner reported. |
| `exceptions-file` | yes | — | Sorted, de-duplicated excepted CVE IDs (may be empty). |
| `dry-run` | no | `false` | A passing image yields `dryrun` instead of `promote`. |
| `missing-sbom-count` | no | `0` | Non-zero forces `blocked-missing-sbom`. |
| `output-dir` | yes | — | Directory for the computed gate files. |

Outputs: `decision`, `blocking-count`, `remaining-count`, `excepted-count`,
`excepted-str`, `remaining-md`, `excepted-md`.

### attach-scan-report

Attach an empty OCI scan-report referrer to a promoted image.

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `image-ref` | yes | — | Promoted image to attach to (`repo:tag`). |
| `source-repo` | yes | — | Repository the image was promoted from. |
| `tag` | yes | — | Tag that was scanned and promoted. |
| `threshold` | yes | — | Severity threshold the image passed. |
| `excepted-str` | no | `""` | Pipe-separated excepted CVEs. |
| `scanner-version` | yes | — | Resolved Trivy version. |
| `method` | no | `image` | Scan method recorded: `image` or `sbom`. |
| `sbom-predicate-type` | no | `""` | Recorded only when `method` is `sbom`. |

The referrer artifact type is `application/vnd.cssc.scan-report.v1+json`; see the
[promote-from-quarantine architecture](../architecture/workflows/promote-from-quarantine-workflows.md#scan-report-referrer-artifact)
for the full annotation schema.

### delete-image

Delete one tag from a GHCR repository via the Packages REST API.

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `repository` | yes | — | GHCR repository, without tag. |
| `tag` | yes | — | Tag to delete. |
| `token` | no | `""` | PAT with `delete:packages`; deletion is skipped when empty. |

Outputs: `status` (`deleted` / `skipped` / `failed`).

## How the actions compose

### Mirror workflow (`_mirror-image.yml`)

A single job: check out, set up `crane` (and `oras` when copying referrers), run
**registry-login** for the source (when authenticated) and GHCR, then
**mirror-image**, then write a summary from its outputs.

### Promote-from-quarantine workflows (`_promote-from-quarantine.yml`, `_promote-from-quarantine-sbom.yml`)

A matrix fan-out across three jobs:

```text
enumerate ──► scan (matrix: one job per tag) ──► summary
   │             │                                  │
   │             ├─ registry-login                  └─ aggregate per-tag
   ├─ registry-login    ├─ scan-image / scan-sbom      result artifacts into
   ├─ resolve severities├─ evaluate-findings           one job summary
   └─ enumerate-tags    ├─ mirror-image (promote)
       → tags-json      ├─ attach-scan-report
                        ├─ delete-image
                        └─ upload result artifact
```

- **enumerate** lists the tags (`enumerate-tags`) and resolves the severity set,
  emitting a JSON tag array consumed by `strategy.matrix`.
- **scan** runs once per tag, in parallel (`fail-fast: false`), chaining the
  single-image actions and uploading a small result artifact.
- **summary** downloads every result artifact and renders one aggregated job
  summary (overview table + per-image detail), so the output matches the old
  monolithic workflow despite the parallel topology.
