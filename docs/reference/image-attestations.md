# CSSC Dashboard image attestations

The CSSC Dashboard application images (built by the
[`build / cssc-dashboard`](../../.github/workflows/build-cssc-dashboard.yml)
workflow) carry build-time attestations attached as **OCI referrers**, so they
travel with the image in GHCR and can be discovered without pulling the image.

## SBOM

An **SPDX** Software Bill of Materials is generated **per platform**
(`linux/amd64`, `linux/arm64`) by BuildKit (`docker buildx build --sbom=true`)
and attached to the image as an in-toto attestation referrer.

### Retrieve

```bash
# Inspect the SBOM(s) via buildx:
docker buildx imagetools inspect \
  ghcr.io/toddysm/apps/cssc-dashboard/packages-service:latest \
  --format '{{ json .SBOM }}'

# Or list referrers directly:
oras discover ghcr.io/toddysm/apps/cssc-dashboard/packages-service:latest
```

The SBOM complements the vulnerability scanning already performed in the
promote-from-quarantine flow; here it is produced at application build time and
describes the final application image contents.

## Provenance

A **SLSA build-provenance** attestation (`mode=max`) is generated **per
platform** by BuildKit (`docker buildx build --provenance=mode=max`) and
attached to the image as an in-toto attestation referrer. It records the
builder, the source repository and revision, the materials (including the base
image digest), and the build parameters.

### Retrieve

```bash
docker buildx imagetools inspect \
  ghcr.io/toddysm/apps/cssc-dashboard/packages-service:latest \
  --format '{{ json .Provenance }}'
```

Together with the manifest annotations (`source`, `revision`, `base.digest`) and
the SBOM, this gives end-to-end build traceability for each image.
