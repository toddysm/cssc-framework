# Image tagging

This guide explains how the `build / cssc-dashboard` workflow **tags** the CSSC
Dashboard images, which tag to use for which purpose, and how to pull by each
tag. It is the companion to the
[reading image annotations](reading-image-annotations.md) guide and the
[image annotations reference](../../reference/image-annotations.md).

## The tag set

Every build publishes each service image (a multi-arch OCI index) under the
same **four** tags derived from the project's semantic version:

| Tag | Example | Mutability | What it points at |
| --- | --- | --- | --- |
| `major` | `0` | Moving | The latest build of the current major line. |
| `minor` | `0.1` | Moving | The latest build of the current minor line. |
| `patch` | `0.1.0` | Moving | The latest build of that exact release. |
| `build` | `0.1.0-69deeec` | Immutable | One specific build (`<release>-<short-sha>`). |

The `build` tag appends the 7-character commit short SHA to the release version,
so it identifies exactly one build and never moves. The `major`, `minor`, and
`patch` tags are **moving**: each build re-points them at the newest image.

> **No `latest`.** The workflow deliberately does **not** publish a `latest`
> tag. `latest` is ambiguous (it silently changes and says nothing about the
> version), so pin one of the tags above instead.

## Where the version comes from

The release version is read from the **latest published GitHub Release** (the
leading `v` is stripped, so a release tagged `v0.1.0` becomes `0.1.0`). The
build fails if there is no published release, because the tags cannot be
derived without one.

## Which tag should I use?

- **Reproducibility / provenance / pinning in manifests** — use the immutable
  **`build`** tag (`0.1.0-69deeec`). It never changes, so a deployment or lock
  file always resolves to the exact same image, and it maps 1:1 to a commit.
- **Track a release line for patches** — use the moving **`patch`** (`0.1.0`)
  or **`minor`** (`0.1`) tag to pick up rebuilds of the same version (for
  example a base-image security refresh) without chasing digests.
- **Always take the newest major build** — use the moving **`major`** (`0`)
  tag. Convenient for demos, but the least predictable.

The immutable `build` tag is also recorded in the
`org.opencontainers.image.version` annotation, and the full set is recorded in
`com.toddysm.image.tags` (see the
[annotations reference](../../reference/image-annotations.md)), so you can recover
every tag from the image itself.

## Pulling by tag

```bash
REPO=ghcr.io/toddysm/apps/cssc-dashboard/packages-service

# Exact, immutable build (recommended for pinning):
docker pull "$REPO:0.1.0-69deeec"

# Latest build of the 0.1 line:
docker pull "$REPO:0.1"

# Latest build of the current major line:
docker pull "$REPO:0"
```

Substitute `issues-service` or `dashboard-web` for the other services.

### Pin by digest for the strongest guarantee

Even an immutable tag is a name; to pin the exact bytes, resolve the digest once
and reference it:

```bash
digest="$(crane digest "$REPO:0.1.0-69deeec")"
docker pull "$REPO@$digest"
```

## Related

- [Reading image annotations](reading-image-annotations.md)
- [Verifying image attestations](verifying-image-attestations.md)
- [Image annotations reference](../../reference/image-annotations.md)
- [Build workflows architecture](../../architecture/build/build-workflows.md)
