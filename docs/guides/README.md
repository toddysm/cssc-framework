# Guides

How-to and operational guides for the `cssc-framework` repository.

- [Mirroring base images from Docker Hub to GHCR](mirroring-base-images.md) —
  how the mirror actions work and how to add a new mirror for another image or
  tag.
- [Configuring human-in-the-loop promotion overrides + Slack notifications](configuring-override-approval.md) —
  how to enable the approve/deny override path for blocked images and wire up
  Slack notifications.
- [Verifying and reading image SBOM and provenance](verifying-image-attestations.md) —
  how to read and cross-check the SBOM and build provenance on the CSSC Dashboard
  images, from both the embedded attestations and the OCI 1.1 referrers.
- [Reading image annotations](reading-image-annotations.md) —
  how to read the OCI manifest annotations stamped onto each build and what each
  one is used for.
