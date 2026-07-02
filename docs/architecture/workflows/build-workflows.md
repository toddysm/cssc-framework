# Build workflows architecture

This document describes the architecture of the GitHub Actions workflow that
builds the demo applications under [`apps/`](../../../apps/) and publishes them
to the GitHub Container Registry (GHCR) with portable supply-chain metadata. It
covers:

1. [How is the workflow structured?](#how-is-the-workflow-structured)
2. [What tooling is used?](#what-tooling-is-used)
3. [How are images tagged?](#how-are-images-tagged)
4. [What metadata is attached?](#what-metadata-is-attached)
5. [What is implemented — and what is not?](#what-is-implemented-and-what-is-not)

For naming and file-system conventions, see
[workflow naming conventions](../../contributing/workflow-naming.md).

## Purpose

The build workflow turns application source under `apps/` into OCI container
images that are **multi-architecture**, carry **supply-chain metadata**
(annotations, SBOM, provenance), and are **versioned with semantic-version
tags** derived from the repository's code release. The images build **on top of
the promoted `golden/*` base images**, so the whole chain — base image, build,
and metadata — stays inside GHCR and under the owner's control.

The first (and currently only) application is the CSSC Dashboard, built by
[`build-cssc-dashboard.yml`](../../../.github/workflows/build-cssc-dashboard.yml)
(display name `build / cssc-dashboard`).

## How is the workflow structured

Unlike the mirror and promote-from-quarantine workflows (which use a
caller + reusable-workflow + composite-action layout), the build workflow is a
**single workflow** with a matrix over the services it produces. Each service is
an independent image built from the same build context
([`apps/python-app`](../../../apps/python-app), which also holds the shared
`libs/cssc_common` library):

```text
.github/workflows/build-cssc-dashboard.yml   # build / cssc-dashboard
  └── job: build (matrix: packages-service, issues-service, dashboard-web)
        ├── Check out
        ├── Set up QEMU / Buildx / ORAS
        ├── Log in to GHCR
        ├── Build and push        (docker buildx build, multi-arch, annotations)
        └── Publish attestations  (extract SBOM/provenance, oras attach referrers)
```

The workflow triggers on pushes to `main` that touch the application sources or
the workflow file, and can be run manually via `workflow_dispatch`:

```yaml
on:
  push:
    branches: [main]
    paths:
      - "apps/python-app/services/**"
      - "apps/python-app/libs/**"
      - ".github/workflows/build-cssc-dashboard.yml"
  workflow_dispatch:
```

Each service image is published to
`ghcr.io/<owner>/apps/cssc-dashboard/<service>`.

## What tooling is used

| Tool | Role |
| ---- | ---- |
| [`docker buildx`](https://docs.docker.com/build/) | Multi-arch (`linux/amd64`, `linux/arm64`) OCI build, manifest/index annotations, embedded SBOM/provenance. |
| [`docker/setup-qemu-action`](https://github.com/docker/setup-qemu-action) | Emulation for cross-architecture builds. |
| [`oras`](https://oras.land) | Re-attaches the SBOM/provenance as OCI 1.1 Referrers-API artifacts. |
| `git` | Resolves the commit SHA and commit time (`SOURCE_DATE_EPOCH`). |
| GitHub Releases | Source of the semantic version used for tagging (see below). |

All third-party actions are pinned by full commit SHA.

## How are images tagged

Images are tagged using a **semantic-version** scheme. The version is taken from
the repository's **code release** (the GitHub Releases page; `0.1.0` at the time
of writing).

### The tags

For a release `X.Y.Z` and a build of commit `sha`, each build applies four tags
to the image (the multi-arch index):

| Tag | Value | Example | Mutability |
| --- | ----- | ------- | ---------- |
| Major | `X` | `0` | Moving — re-pointed to the newest build in the major line. |
| Minor | `X.Y` | `0.1` | Moving — re-pointed to the newest build in the minor line. |
| Patch | `X.Y.Z` | `0.1.0` | Moving — re-pointed to the newest build of that release. |
| Build | `X.Y.Z-<short-sha>` | `0.1.0-69deeec` | **Immutable** — unique per commit. |

- The **build tag** is the canonical, immutable reference for a specific image;
  consumers that need reproducibility pin to it.
- The **major/minor/patch** tags are moving pointers for consumers that want to
  automatically pick up newer builds within a compatibility line.
- The short commit SHA is a **fixed 7 characters** for consistency
  (`0.1.0-69deeec`).
- Images are **never** tagged `latest`. A floating `latest` hides which version
  is actually deployed and encourages non-reproducible pulls; the moving
  major/minor tags cover the "track the newest" use case explicitly.

### Resolving the version

The build resolves the semantic version from the **latest published GitHub
Release** and strips an optional leading `v` (so both `0.1.0` and `v0.1.0`
yield `0.1.0`). The major and minor components are derived from that string.

### Decisions

These decisions are settled here so the implementation (#125) has no ambiguity;
they can be revisited in review:

- **Version source = latest published GitHub Release.** Releases are the
  human-curated signal of "what version are we shipping", decoupled from every
  commit. (An alternative — a `VERSION` file in the repo — was not chosen, to
  keep a single source of truth on the Releases page.)
- **No release ⇒ the build fails** with a clear message. Tagging requires a
  released version; cut a release before building. This is a deliberate gate
  rather than silently falling back to `0.0.0`.
- **Fixed 7-char short SHA** for a predictable, collision-resistant build tag.
- **Moving tags are updated on every build**, always pointing at the most recent
  build in their line.
- **Tags apply to the multi-arch index**; all four tags reference the same
  index digest.

## What metadata is attached

Every image carries OCI **manifest annotations** at both the index and the
per-platform manifest scope, plus **SBOM** and **provenance** attestations. The
full annotation set and attestation details are documented in the reference
docs:

- [Image annotations](../../reference/image-annotations.md)
- [Image attestations](../../reference/image-attestations.md)

### Annotation changes for semver tagging

The tagging work (#123) adjusts the annotation set as follows:

| Annotation | Before | After |
| ---------- | ------ | ----- |
| `org.opencontainers.image.version` | short commit SHA | the **immutable build tag** (`0.1.0-69deeec`) |
| `com.toddysm.image.lineage` | — (new) | the **minor** version (`0.1`) |
| `com.toddysm.image.tags` | — (new) | all tags, pipe-separated, major→build (`0\|0.1\|0.1.0\|0.1.0-69deeec`) |

`com.toddysm.image.lineage` gives a stable grouping key for "all builds of a
minor line", and `com.toddysm.image.tags` records exactly which tags a build was
published under (useful because the moving tags will later point elsewhere).

### Reproducibility

`org.opencontainers.image.created` and layer timestamps are derived from the
commit time via `SOURCE_DATE_EPOCH`, and the base image is pinned by digest
(`org.opencontainers.image.base.digest`). This removes timestamp
nondeterminism; full bit-for-bit reproducibility additionally depends on stable
dependency resolution (for example `pip`).

## What is implemented — and what is not

**Implemented today**

- Multi-arch (`linux/amd64`, `linux/arm64`) OCI images per service.
- Manifest/index annotations (standard `org.opencontainers.image.*` + custom
  `com.toddysm.*`).
- SPDX SBOM and SLSA provenance, both embedded and published as OCI 1.1
  referrers.
- Semantic-version tagging (major/minor/patch/build) sourced from the code
  release, with no `latest` tag.
- `version` = immutable build tag; `com.toddysm.image.lineage` and
  `com.toddysm.image.tags` annotations.

**Deliberately out of scope**

- **Cryptographic signing** of images or attestations (e.g. cosign / Sigstore).
  The attestations are currently unsigned; signing is a possible future
  enhancement.
- **Runtime deployment** — handled separately by the Helm charts under
  `apps/*/deploy`.

## Related

- [`build / cssc-dashboard` workflow](../../../.github/workflows/build-cssc-dashboard.yml)
- [Image annotations (reference)](../../reference/image-annotations.md)
- [Image attestations (reference)](../../reference/image-attestations.md)
- [CSSC Dashboard application architecture](../apps/cssc-dashboard.md)
- [Workflow naming conventions](../../contributing/workflow-naming.md)
