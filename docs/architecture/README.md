# Architecture

Design and architecture documentation for the `cssc-framework` repository.

## Topics

- [Workflow architecture](workflows/) — GitHub Actions workflows.
  - [Image mirror workflows](workflows/image-mirror-workflows.md) — mirroring
    upstream base images from Docker Hub into GHCR.
  - [Build workflows](workflows/build-workflows.md) — building the demo apps into
    versioned, multi-arch images with supply-chain metadata.
- [Application architecture](apps/) — sample applications.
  - [CSSC Dashboard](apps/cssc-dashboard.md) — microservices web app that
    visualizes the CSSC framework stage by stage.
