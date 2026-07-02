# CSSC Dashboard image annotations

The CSSC Dashboard application images (built by the
[`build / cssc-dashboard`](../../.github/workflows/build-cssc-dashboard.yml)
workflow) are **OCI**, **multi-arch** (`linux/amd64`, `linux/arm64`), and carry
OCI **manifest annotations** so supply-chain metadata travels with the image.

For how those images are **tagged** (the semantic-version tag set and which
tag to pin), see the [image tagging guide](../guides/image-tagging.md).

Annotations are set at **both** the multi-arch **index** and each **per-platform
manifest**, so they are visible regardless of which descriptor a tool inspects:

```bash
crane manifest ghcr.io/toddysm/apps/cssc-dashboard/packages-service:0.1 | jq .annotations
```

## Standard annotations (`org.opencontainers.image.*`)

| Annotation | Value |
| ---------- | ----- |
| `created` | Build time derived from the commit time (`SOURCE_DATE_EPOCH`) — reproducible. |
| `source` | The source repository URL. |
| `revision` | The full commit SHA the image was built from. |
| `version` | The immutable build tag `<release>-<short-sha>` (e.g. `0.1.0-69deeec`) the image is published under. |
| `title` | `CSSC Dashboard <service>`. |
| `description` | One-line service description. |
| `url` | Project URL. |
| `documentation` | Link to the CSSC Dashboard design doc. |
| `vendor` | `toddysm.com`. |
| `licenses` | `Apache-2.0`. |
| `base.name` | The base image **name only** (e.g. `ghcr.io/toddysm/golden/python`). |
| `base.digest` | The base image digest the image was built on. |

> **Note on `base.name`.** The OCI image spec defines
> `org.opencontainers.image.base.name` as the *full* base reference (including
> the tag). This project deliberately stores the **name only** there and keeps
> the tag in the custom `com.toddysm.image.base.tag` annotation (below), so the
> name, tag, and digest are independently addressable. Tools that expect the
> full reference in `base.name` should compose it as
> `base.name + ":" + com.toddysm.image.base.tag`.

## Custom annotations (`com.toddysm.*`)

| Annotation | Value |
| ---------- | ----- |
| `com.toddysm.image.base.tag` | The base image tag (e.g. `3.14-slim`). |
| `com.toddysm.image.lineage` | The minor-version lineage the image belongs to (e.g. `0.1`). |
| `com.toddysm.image.tags` | Every tag applied to the image, `\|`-separated, from `major` to `build` (e.g. `0\|0.1\|0.1.0\|0.1.0-69deeec`). |
| `com.toddysm.build.workflow` | The building workflow display name. |
| `com.toddysm.build.run-url` | Link to the exact GitHub Actions run. |

## Reproducibility

`created` and layer timestamps are derived from the commit time via
`SOURCE_DATE_EPOCH`, which makes those timestamps deterministic, and the build
pins the base image by digest (`base.digest`). Full bit-for-bit digest
reproducibility additionally depends on stable dependency resolution (for
example `pip`), so `SOURCE_DATE_EPOCH` removes timestamp nondeterminism but is
not a guarantee on its own.
