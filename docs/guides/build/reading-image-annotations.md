# Reading image annotations

This guide shows how to read the **OCI manifest annotations** that the
`build / cssc-dashboard` workflow stamps onto every CSSC Dashboard image, and
explains **what each annotation is for**.

It is the task-oriented companion to the reference document
[image annotations](../../reference/image-annotations.md), which lists the
annotation set. If you only want the list, read that document; if you want to
*read* the annotations off a built image and understand how to use them, read
this one.

## Contents

- [What annotations are and why they exist](#what-annotations-are-and-why-they-exist)
- [Prerequisites](#prerequisites)
- [Reading the annotations](#reading-the-annotations)
- [Index scope vs. per-platform scope](#index-scope-vs-per-platform-scope)
- [What each annotation is for](#what-each-annotation-is-for)
- [Worked examples](#worked-examples)
- [Troubleshooting](#troubleshooting)

## What annotations are and why they exist

OCI **annotations** are key/value metadata carried *in the image manifest* (and
in the multi-arch index). Unlike labels baked into the container config, they
travel with the image in the registry and can be read **without pulling** the
image, which makes them ideal for supply-chain metadata: where the image came
from, what commit and base image it was built on, and which CI run produced it.

The build workflow writes annotations at **both** the multi-arch **index** and
each **per-platform manifest**, so the metadata is visible regardless of which
descriptor a tool inspects.

Throughout this guide the example image is:

```text
ghcr.io/toddysm/apps/cssc-dashboard/packages-service:0.1
```

Substitute `issues-service` or `dashboard-web` for the other services.

## Prerequisites

Any one of these CLIs can read annotations; install what you have:

- [`crane`](https://github.com/google/go-containerregistry/tree/main/cmd/crane)
  — `crane manifest` prints the raw manifest JSON.
- [`docker`](https://docs.docker.com/get-docker/) with Buildx —
  `docker buildx imagetools inspect`.
- [`oras`](https://oras.land) — `oras manifest fetch`.
- [`skopeo`](https://github.com/containers/skopeo) — `skopeo inspect --raw`.
- [`jq`](https://jqlang.github.io/jq/) — to filter the JSON.

The images are public, so anonymous reads work. For a private repository, log in
first (`docker login ghcr.io`); all of the tools above reuse
`~/.docker/config.json`.

## Reading the annotations

Read **all** index-level annotations:

```bash
IMAGE=ghcr.io/toddysm/apps/cssc-dashboard/packages-service:0.1

# crane
crane manifest "$IMAGE" | jq '.annotations'

# oras
oras manifest fetch "$IMAGE" | jq '.annotations'

# docker buildx
docker buildx imagetools inspect "$IMAGE" --raw | jq '.annotations'

# skopeo
skopeo inspect --raw "docker://$IMAGE" | jq '.annotations'
```

Read a **single** annotation:

```bash
crane manifest "$IMAGE" | jq -r '.annotations["org.opencontainers.image.revision"]'
```

## Index scope vs. per-platform scope

The commands above read the **index** (the descriptor the tag points to). The
same annotations are also present on each **per-platform manifest**. To read them
at platform scope, resolve the platform digest first:

```bash
REPO=ghcr.io/toddysm/apps/cssc-dashboard/packages-service

# Pick a platform digest:
crane manifest "$REPO:0.1" \
  | jq -r '.manifests[]
      | select(.platform.os != "unknown")
      | "\(.platform.os)/\(.platform.architecture)\t\(.digest)"'

# Read that platform manifest's annotations:
crane manifest "$REPO@sha256:<platform-digest>" | jq '.annotations'
```

Both scopes carry the same values, so for everyday use the index-level read is
enough; the per-platform read matters only when a tool inspects a specific
architecture.

## What each annotation is for

### Standard annotations (`org.opencontainers.image.*`)

| Annotation | Value | What it is used for |
| --- | --- | --- |
| `org.opencontainers.image.created` | Build time from the commit (`SOURCE_DATE_EPOCH`) | Reproducible build timestamp; auditing and sorting images by when they were built. |
| `org.opencontainers.image.source` | Source repository URL | Jump from a running image back to the code; scanners link findings to the repo. |
| `org.opencontainers.image.revision` | Full commit SHA | Pinpoint the exact source the image was built from; reproduce or bisect a build. |
| `org.opencontainers.image.version` | Immutable build tag `<release>-<short-sha>` (e.g. `0.1.0-69deeec`) | The exact immutable tag the image is published under; the build also applies the moving `major`/`minor`/`patch` tags (e.g. `0`, `0.1`, `0.1.0`) and never `latest`, and records the immutable build tag here so you can map a running image back to the precise build. |
| `org.opencontainers.image.title` | `CSSC Dashboard <service>` | Display name shown in registry UIs and tooling. |
| `org.opencontainers.image.description` | One-line service description | Quick human context about what the image does. |
| `org.opencontainers.image.url` | Project URL | Landing page for the project. |
| `org.opencontainers.image.documentation` | Link to the design doc | Deep-dive documentation for operators. |
| `org.opencontainers.image.vendor` | `toddysm.com` | Ownership/attribution; policy engines can assert a trusted vendor. |
| `org.opencontainers.image.licenses` | `Apache-2.0` (SPDX id) | License-compliance scanning and inventory. |
| `org.opencontainers.image.base.name` | Base image **name only** | Which base family the image is built on; policy can require `golden/*` bases. |
| `org.opencontainers.image.base.digest` | Base image digest | The exact base that was pinned; correlate base-image CVEs and cross-check against the provenance materials. |

> **`base.name` deviation.** The OCI spec defines `base.name` as the *full*
> reference (with tag). This project stores the **name only** there and keeps the
> tag separately in `com.toddysm.image.base.tag`, so name, tag, and digest are
> independently addressable. Reconstruct the full reference as
> `base.name + ":" + com.toddysm.image.base.tag` (see [Worked examples](#worked-examples)).

### Custom annotations (`com.toddysm.*`)

| Annotation | Value | What it is used for |
| --- | --- | --- |
| `com.toddysm.image.base.tag` | Base image tag (e.g. `3.14-slim`) | The human base tag; combine with `base.name`/`base.digest` to form the full base reference. |
| `com.toddysm.image.lineage` | Minor-version lineage (e.g. `0.1`) | The moving minor line the image belongs to; group or pin images by a compatible lineage. |
| `com.toddysm.image.tags` | Every tag applied to the image, `\|`-separated (e.g. `0\|0.1\|0.1.0\|0.1.0-69deeec`) | The full tag set the build published, from most-moving (`major`) to immutable (`build`); recover every tag from the image itself. |
| `com.toddysm.build.workflow` | Building workflow display name | Which workflow produced the image; auditing the build path. |
| `com.toddysm.build.run-url` | Link to the exact GitHub Actions run | Jump straight to the CI run that built the image for logs and provenance. |
| `com.toddysm.security.policy` | Link to the repository security policy | Find out how vulnerabilities in the image are handled and disclosed. |
| `com.toddysm.security.reporturl` | URL for reporting a vulnerability | Report a vulnerability programmatically (the GitHub private advisory intake). |

## Worked examples

**Reconstruct the full base image reference** from the split annotations:

```bash
m=$(crane manifest "$IMAGE")
name=$(jq -r '.annotations["org.opencontainers.image.base.name"]'   <<<"$m")
tag=$(jq -r  '.annotations["com.toddysm.image.base.tag"]'           <<<"$m")
dig=$(jq -r  '.annotations["org.opencontainers.image.base.digest"]' <<<"$m")
echo "${name}:${tag}@${dig}"
# -> ghcr.io/toddysm/golden/python:3.14-slim@sha256:...
```

**Open the CI run that built the image:**

```bash
crane manifest "$IMAGE" | jq -r '.annotations["com.toddysm.build.run-url"]'
```

**Print a compact provenance summary:**

```bash
crane manifest "$IMAGE" | jq -r '.annotations | {
  created:  ."org.opencontainers.image.created",
  revision: ."org.opencontainers.image.revision",
  source:   ."org.opencontainers.image.source",
  base:     ."org.opencontainers.image.base.name",
  base_tag: ."com.toddysm.image.base.tag",
  base_dig: ."org.opencontainers.image.base.digest",
  run:      ."com.toddysm.build.run-url"
}'
```

**Cross-check the base digest against the build provenance** (see the
[attestation verification guide](verifying-image-attestations.md)): the
`base.digest` annotation should appear in the SLSA provenance `materials`.

## Troubleshooting

- **`.annotations` is `null`.** You may have inspected a config or a single-arch
  reference that carries no annotations, or an older image built before the
  annotation work landed. Inspect the multi-arch tag with `crane manifest`.
- **A tool shows annotations on the index but not the platform image (or vice
  versa).** Both scopes are populated; make sure you fetched the descriptor you
  intended (tag/index vs. `@sha256:` platform digest).
- **`base.name` has no tag.** That is intentional — the tag lives in
  `com.toddysm.image.base.tag`. See the deviation note above.
- **`unauthorized` / `denied`.** Log in to GHCR; the tools read
  `~/.docker/config.json`.

## Related

- [Image annotations (reference)](../../reference/image-annotations.md)
- [Verifying and reading image SBOM and provenance](verifying-image-attestations.md)
- [`build / cssc-dashboard` workflow](../../../.github/workflows/build-cssc-dashboard.yml)
