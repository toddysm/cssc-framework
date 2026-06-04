# Workflow architecture

Architecture documentation for the GitHub Actions workflows in this repository.

Workflows fall into two categories (see
[workflow naming conventions](../../contributing/workflow-naming.md)):

| Category | Purpose | Status |
| -------- | ------- | ------ |
| **Mirror** | Copy / refresh upstream base images from Docker Hub into GHCR | Implemented |
| **Build** | Build the demo applications under `apps/` on top of mirrored bases | Planned |

## Documents

- [Image mirror workflows](image-mirror-workflows.md) — how the Docker Hub →
  GHCR mirroring actions are structured, the tooling they use, and what they do
  and deliberately do not do.
