# CSSC Dashboard image attestations

The CSSC Dashboard application images (built by the
[`build / cssc-dashboard`](../../.github/workflows/build-cssc-dashboard.yml)
workflow) carry build-time attestations that are both **embedded** in the image
index (as BuildKit attestation-manifests) and **published as OCI 1.1
Referrers-API artifacts** with `oras attach`. The referrers travel with the
image in GHCR and are discoverable via the Referrers API (`oras discover`)
without pulling the image.

> Referrers attach to the **platform** manifest (not the tag/index), so the
> retrieval commands below target a per-platform digest.

## SBOM

An **SPDX** Software Bill of Materials is generated **per platform**
(`linux/amd64`, `linux/arm64`) by BuildKit (`docker buildx build --sbom=true`)
and published on the platform manifest as an OCI 1.1 referrer (artifact type
`application/vnd.in-toto+json`, `in-toto.io/predicate-type:
https://spdx.dev/Document`).

### Retrieve

```bash
# Referrers attach to the platform manifest, so resolve the platform digests:
crane manifest ghcr.io/toddysm/apps/cssc-dashboard/packages-service:latest \
  | jq -r '.manifests[]
      | select(.platform.os != "unknown")
      | "\(.platform.os)/\(.platform.architecture)\t\(.digest)"'

# List the OCI 1.1 referrers attached to a platform manifest:
oras discover --format tree \
  ghcr.io/toddysm/apps/cssc-dashboard/packages-service@<platform-digest>

# Pull the SPDX in-toto statement (referrer digest from the step above):
oras pull -o sbom \
  ghcr.io/toddysm/apps/cssc-dashboard/packages-service@<referrer-digest>

# Alternatively, read the embedded attestation via buildx:
docker buildx imagetools inspect \
  ghcr.io/toddysm/apps/cssc-dashboard/packages-service:latest \
  --format '{{ json .SBOM }}'
```

The SBOM complements the vulnerability scanning already performed in the
promote-from-quarantine flow; here it is produced at application build time and
describes the final application image contents.

## Provenance

A **SLSA build-provenance** attestation (`mode=max`) is generated **per
platform** by BuildKit (`docker buildx build --provenance=mode=max`) and
published on the platform manifest as an OCI 1.1 referrer (artifact type
`application/vnd.in-toto+json`, `in-toto.io/predicate-type:
https://slsa.dev/provenance/v0.2`). It records the builder, the source
repository and revision, the materials (including the base image digest), and
the build parameters.

### Retrieve

```bash
# List the referrers on a platform manifest (see the SBOM section for how to
# resolve <platform-digest>) and pull the SLSA in-toto statement:
oras discover --format tree \
  ghcr.io/toddysm/apps/cssc-dashboard/packages-service@<platform-digest>
oras pull -o provenance \
  ghcr.io/toddysm/apps/cssc-dashboard/packages-service@<referrer-digest>

# Alternatively, read the embedded attestation via buildx:
docker buildx imagetools inspect \
  ghcr.io/toddysm/apps/cssc-dashboard/packages-service:latest \
  --format '{{ json .Provenance }}'
```

Together with the manifest annotations (`source`, `revision`, `base.digest`) and
the SBOM, this gives end-to-end build traceability for each image.
