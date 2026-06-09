# Workflow naming conventions

This repository uses GitHub Actions for two distinct purposes that must never be
confused with each other: **mirroring** upstream base images into GitHub
Container Registry (GHCR), and **building** the demo applications on top of those
bases. The naming convention below keeps the two categories clearly separated,
both in the file system and in the Actions UI.

## Categories

| Category | Purpose | Workflow file | Display `name:` | Concurrency group |
| -------- | ------- | ------------- | --------------- | ----------------- |
| **Mirror** | Copy / refresh a base image from an upstream registry into GHCR | `mirror-<image>.yml` | `mirror / quarantine/<image>` | `mirror-quarantine-<image>` |
| **Promote from quarantine** | Scan a quarantined image and promote it into `golden/<image>` when it passes the vulnerability policy | `promote-from-quarantine-<image>.yml` | `promote from quarantine / quarantine/<image>` | `promote-from-quarantine-<image>` |
| **Build** | Build an application image on top of a mirrored base | `build-<app>.yml` | `build / <app>` | `build-<app>` |
| **Reusable** | Shared logic invoked by other workflows; never triggered directly | `_<purpose>.yml` (leading underscore) | `_reusable / <purpose>` | n/a |
| **Composite action** | A single reusable step shared across workflows | `.github/actions/<verb-noun>/action.yml` | `name: <verb-noun>` | n/a |

### Rules

1. **Verb prefix.** Every workflow filename starts with a category verb:
   `mirror-`, `promote-from-quarantine-`, `build-`, or a leading underscore
   (`_`) for reusable
   workflows. This groups related workflows together alphabetically and makes
   intent obvious at a glance.
2. **Leading underscore = internal.** Reusable workflows (triggered by
   `workflow_call`) are prefixed with `_` so they sort to the top of the list
   and signal "do not run me directly."
3. **Display names use a `category / subject` format** (for example
   `mirror / quarantine/python`) so the Actions sidebar reads cleanly.
4. **Concurrency groups** mirror the filename so two runs of the same logical
   job never overlap, while different images/apps run independently.
5. **GHCR destination repositories** for mirrored base images follow the
   `quarantine/<image>` scheme, e.g. `ghcr.io/<owner>/quarantine/python`.
   Images promoted out of quarantine by a promote-from-quarantine workflow
   follow the
   `golden/<image>` scheme, e.g. `ghcr.io/<owner>/golden/python`.

## Mirror workflows

Mirror workflows keep a copy of an upstream base image fresh in GHCR.

- **Structure.** Logic lives in a single reusable workflow,
  [`_mirror-image.yml`](../../.github/workflows/_mirror-image.yml), which is
  assembled from composite actions under `.github/actions/` (see
  [workflow actions](../reference/workflow-actions.md)). Each image
  has a thin caller, e.g.
  [`mirror-python.yml`](../../.github/workflows/mirror-python.yml), that only
  declares triggers and the image-specific inputs and calls the reusable
  workflow via `uses:`.
- **Idempotent sync.** On every run the workflow compares the digest of the
  source tag against the digest already in GHCR and only copies when they
  differ. `crane copy` preserves multi-architecture manifest lists.
- **Triggers.** A daily `schedule` (06:00 UTC) plus `workflow_dispatch` with an
  optional `force` input to copy even when digests match.
- **Auth.** GHCR is accessed with the built-in `GITHUB_TOKEN`
  (`packages: write`). Public Docker Hub sources are pulled anonymously.

### Adding a new mirror workflow

1. Copy `mirror-python.yml` to `mirror-<image>.yml`.
2. Update the display `name:`, the `concurrency.group`, and the four inputs
   (`source_image`, `source_tag`, `dest_image`, `dest_tag`).
3. No logic changes are needed — the reusable workflow does the work.

## Promote-from-quarantine workflows

Promote-from-quarantine workflows gate images out of quarantine. They scan every
tag in a
`quarantine/<image>` repository with Trivy and promote the images that pass a
configurable severity threshold (plus an optional CVE exception list) into a
`golden/<image>` repository.

- **Structure.** Logic lives in a single reusable workflow,
  [`_promote-from-quarantine.yml`](../../.github/workflows/_promote-from-quarantine.yml), which is
  assembled from composite actions under `.github/actions/` (see
  [workflow actions](../reference/workflow-actions.md)) and fans the work out
  across a job matrix (one job per tag). Each scanned
  repository has a thin caller, e.g.
  [`promote-from-quarantine-python.yml`](../../.github/workflows/promote-from-quarantine-python.yml), that only
  declares triggers and the repository-specific inputs and calls the reusable
  workflow via `uses:`.
- **Gate + promote.** Passing images are copied with `crane copy`, get an empty
  OCI scan-report referrer attached with `oras attach`, and are then deleted
  from quarantine. Blocked images stay in quarantine.
- **Triggers.** A daily `schedule` (07:00 UTC, after the 06:00 mirror) plus
  `workflow_dispatch` with overrides for the threshold, exceptions, and a
  `dry_run` mode.
- **Auth.** GHCR scan/copy/attach use the built-in `GITHUB_TOKEN`
  (`packages: write`). Deleting quarantine tags needs a separate
  `delete:packages` PAT (see the
  [promote-from-quarantine architecture](../architecture/workflows/promote-from-quarantine-workflows.md)).

### Adding a new promote-from-quarantine workflow

1. Copy `promote-from-quarantine-python.yml` to `promote-from-quarantine-<image>.yml`.
2. Update the display `name:`, the `concurrency.group`, and the inputs
   (`source_repo`, `dest_repo`, and any threshold/exception overrides).
3. No logic changes are needed — the reusable workflow does the work.

## Build workflows

Build workflows (added later) build the demo applications under `apps/` on top
of the mirrored base images. They use the `build-<app>.yml` filename and the
`build / <app>` display name so they remain clearly separate from mirror
workflows.

## Composite actions

The reusable steps shared across workflows live as **composite actions** under
[`.github/actions/`](../../.github/actions/), one directory per action with an
`action.yml` inside. They are the single source of truth for each operation
(login, enumerate, copy, scan, gate, attach, delete); the reusable workflows
only orchestrate them.

### Rules

1. **One verb-noun per action.** Action directory and `name:` use the standard
   terminology verb-noun, e.g. `registry-login`, `enumerate-tags`,
   `mirror-image`, `scan-image`, `scan-sbom`, `evaluate-findings`,
   `attach-scan-report`, `delete-image`. The canonical glossary lives in
   [workflow actions and terminology](../reference/workflow-actions.md).
2. **kebab-case** for action directory names, inputs, and outputs.
3. **Single responsibility.** An action does one thing on one image/repository;
   looping over many tags is the orchestrating workflow's job (via a matrix).
4. **No tool setup inside actions.** Actions assume the calling job has already
   checked out the repo and installed the CLIs they need (`crane`, `oras`,
   `trivy`); this lets several actions share one setup.
5. **Document every action** in
   [workflow actions and terminology](../reference/workflow-actions.md) when it
   is added or its interface changes.
