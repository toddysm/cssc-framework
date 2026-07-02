# Workflow architecture

Architecture documentation for the GitHub Actions workflows in this repository.

Workflows fall into the following categories (see
[workflow naming conventions](../../contributing/workflow-naming.md)):

| Category | Purpose | Status |
| -------- | ------- | ------ |
| **Mirror** | Copy / refresh upstream base images from Docker Hub into GHCR | Implemented |
| **Promote from quarantine** | Scan quarantined images and promote the ones that pass a vulnerability policy into `golden/<image>` (or `base/...` for base/hardened images) | Implemented |
| **Build** | Build the demo applications under `apps/` on top of promoted `golden/*` bases, tag them with semantic versions, and attach supply-chain metadata | Implemented |
| **Report** | Watch other workflows and file/close CI-failure tracking issues | Implemented |

## Documents

- [Image mirror workflows](image-mirror-workflows.md) — how the Docker Hub →
  GHCR mirroring actions are structured, the tooling they use, and what they do
  and deliberately do not do.
- [Promote-from-quarantine workflows](promote-from-quarantine-workflows.md) — how quarantined
  images are scanned with Trivy, gated on a severity threshold plus CVE
  exceptions, promoted into `golden/<image>` (or `base/...` for base/hardened
  images) with a scan-report referrer, and
  removed from quarantine.
- [CI failure notifications](ci-failure-notifications.md) — how a
  `workflow_run` monitor opens and closes per-workflow CI-failure tracking
  issues (and optional Slack alerts) when a monitored workflow run fails or
  recovers.
- [Build workflows](build-workflows.md) — how the demo applications are built
  into multi-arch OCI images, tagged with semantic versions, and stamped with
  annotations, SBOM, and provenance.
