# Documentation

Documentation for the `cssc-framework` repository. Content is organized by
topic so each area can grow independently.

## Structure

| Folder | Purpose |
| ------ | ------- |
| [`contributing/`](contributing/) | Guides and conventions for people contributing to this repository. |
| [`architecture/`](architecture/) | Design and architecture documentation. |
| [`guides/`](guides/) | How-to and operational guides. |
| [`reference/`](reference/) | Reference material and conventions. |

## Guides

- [Mirroring base images from Docker Hub to GHCR](guides/mirroring-base-images.md)
  — how the mirror actions work and how to add a new mirror for another image or
  tag.

## Architecture docs

- [Image mirror workflows](architecture/workflows/image-mirror-workflows.md) —
  how the Docker Hub → GHCR mirroring GitHub Actions are structured, the tooling
  they use, and what they do and do not do.
- [CSSC Dashboard application](architecture/apps/cssc-dashboard.md) — a
  microservices web app that visualizes the CSSC framework stage by stage.

## Contributing docs

- [Workflow naming conventions](contributing/workflow-naming.md) — how GitHub
  Actions workflows are named and organized in this repository.
