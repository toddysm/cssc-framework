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
| **Build** | Build an application image on top of a mirrored base | `build-<app>.yml` | `build / <app>` | `build-<app>` |
| **Reusable** | Shared logic invoked by other workflows; never triggered directly | `_<purpose>.yml` (leading underscore) | `_reusable / <purpose>` | n/a |

### Rules

1. **Verb prefix.** Every workflow filename starts with a category verb:
   `mirror-`, `build-`, or a leading underscore (`_`) for reusable workflows.
   This groups related workflows together alphabetically and makes intent
   obvious at a glance.
2. **Leading underscore = internal.** Reusable workflows (triggered by
   `workflow_call`) are prefixed with `_` so they sort to the top of the list
   and signal "do not run me directly."
3. **Display names use a `category / subject` format** (for example
   `mirror / quarantine/python`) so the Actions sidebar reads cleanly.
4. **Concurrency groups** mirror the filename so two runs of the same logical
   job never overlap, while different images/apps run independently.
5. **GHCR destination repositories** for mirrored base images follow the
   `quarantine/<image>` scheme, e.g. `ghcr.io/<owner>/quarantine/python`.

## Mirror workflows

Mirror workflows keep a copy of an upstream base image fresh in GHCR.

- **Structure.** Logic lives in a single reusable workflow,
  [`_mirror-image.yml`](../../.github/workflows/_mirror-image.yml). Each image
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

## Build workflows

Build workflows (added later) build the demo applications under `apps/` on top
of the mirrored base images. They use the `build-<app>.yml` filename and the
`build / <app>` display name so they remain clearly separate from mirror
workflows.
