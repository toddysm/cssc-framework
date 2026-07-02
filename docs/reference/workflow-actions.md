# Workflow actions and terminology

This repository's GitHub Actions are built from small, single-purpose
__composite actions__ under [`.github/actions/`](../../.github/actions/). The
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
| __registry-login__ | Authenticate the local clients to a registry. | "Log in to GHCR", "Log in to source registry" |
| __enumerate-tags__ | List the tags in a repository. | "Enumerate quarantine tags", "list tags" |
| __mirror-image__ | Idempotently copy one image between registries (digest-compare + copy). | "compare digests and copy", "crane copy" |
| __promote-image__ | Copy a passing image from quarantine into golden/base. Implemented as __mirror-image__ with `force: true`. | "promote", "promote passing images" |
| __copy-referrers__ | Copy an image together with its OCI referrers (`oras cp -r` + per-platform children). Folded into __mirror-image__ via `copy-referrers: true`. | "copy_referrers", "copy with referrers" |
| __scan-image__ | Scan one image filesystem with `trivy image`. | "scan images with Trivy" |
| __scan-sbom__ | Scan one image's per-platform SBOM attestations with `trivy sbom`. | "scan platform SBOMs" |
| __evaluate-findings__ | Apply the severity threshold + CVE exceptions to produce a gate decision. | "gate on scan findings" |
| __attach-scan-report__ | Attach the OCI scan-report referrer to a promoted image. | "attach scan-report attestation" |
| __delete-image__ | Delete one tag from a GHCR repository via the Packages API. | "delete promoted tags from quarantine" |

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
| `override` | no | `false` | Records a manual override (promoted despite a failing gate). |
| `override-approver` | no | `""` | Login that approved the override (when `override` is true). |
| `override-issue` | no | `""` | Tracking-issue URL for the override (when `override` is true). |
| `override-cves` | no | `""` | Pipe-separated CVEs that were overridden (when `override` is true). |

The referrer artifact type is `application/vnd.cssc.scan-report.v1+json`; see the
[promote-from-quarantine architecture](../architecture/catalog/promote-from-quarantine-workflows.md#scan-report-referrer-artifact)
for the full annotation schema.

### delete-image

Delete one tag from a GHCR repository via the Packages REST API.

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `repository` | yes | — | GHCR repository, without tag. |
| `tag` | yes | — | Tag to delete. |
| `token` | no | `""` | PAT with `delete:packages`; deletion is skipped when empty. |

Outputs: `status` (`deleted` / `skipped` / `failed`).

### notify-slack

Post a promotion-event or CI-failure message to a Slack incoming webhook. A no-op (with a
warning) when `webhook-url` is empty.

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `webhook-url` | no | `""` | Slack incoming webhook URL; empty disables the action. |
| `status` | yes | — | Message template: `blocked-pending`, `approved`, `denied`, or `ci-failure`. |
| `image` | no* | `""` | Source repository. *Required for `blocked-pending`/`approved`/`denied`; unused for `ci-failure`. |
| `tag` | no* | `""` | Image tag. *Required for the promotion templates; unused for `ci-failure`. |
| `workflow` | no* | `""` | Workflow display name. *Required for `ci-failure`. |
| `threshold` | no | `""` | Severity threshold the image failed. |
| `blocking-cves` | no | `""` | Human-readable blocking-CVE summary. |
| `issue-url` | no | `""` | Link to the tracking issue. |
| `run-url` | no | `""` | Link to the workflow run. |
| `approver` | no | `""` | Login recorded for approved/denied messages. |

### manage-issue

Create, update, comment on, close, or read a promotion tracking issue via `gh`
(needs `issues: write`).

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `operation` | yes | — | `open-or-update`, `comment`, `close`, or `get`. |
| `image` | yes | — | Source repository (dedupe + metadata). |
| `tag` | yes | — | Image tag (dedupe + metadata). |
| `metadata-json` | no | `""` | Machine-readable JSON embedded in the body (`open-or-update`). |
| `body` | no | `""` | Human-readable body / comment text. |
| `outcome` | no | `""` | `close` only: `promotion-approved` or `promotion-denied`. |
| `issue-number` | no | `""` | Target issue; resolved by title when empty. |
| `token` | yes | — | `GITHUB_TOKEN` with `issues: write`. |

Dedupes by the `promotion-pending` label plus a deterministic title
(`Promotion blocked: <image>:<tag>`). Outputs: `issue-number`, `issue-url`,
`metadata-json` (parsed back out of an existing issue).

### verify-approver

Verify an actor meets a minimum repository permission before an override is
honored.

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `actor` | yes | — | The login that issued the command. |
| `min-permission` | no | `maintain` | Minimum permission: `admin`, `maintain`, or `write`. |
| `fail-on-unauthorized` | no | `true` | Fail the step when the actor is below the threshold. |
| `token` | yes | — | Token able to read collaborator permissions. |

Outputs: `authorized` (`true` / `false`).

### manage-failure-issue

Open/update or close a per-workflow **CI-failure** tracking issue via `gh` (needs
`issues: write`). Deduped by the `ci-failure` label plus the title
`CI failure: <workflow>`. Separate from `manage-issue`, which is specific to the
promotion override flow.

| Input | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `operation` | yes | — | `open-or-update` or `close`. |
| `workflow` | yes | — | Workflow display name (dedupe key). |
| `run-url` | no | `""` | Link to the workflow run. |
| `run-number` | no | `""` | Run number of the failed/recovered run. |
| `branch` | no | `""` | Branch the run executed on. |
| `event` | no | `""` | Event that triggered the run. |
| `token` | yes | — | `GITHUB_TOKEN` with `issues: write`. |

Outputs: `issue-number`, `issue-url`.

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
