# Documentation

Documentation for the `cssc-framework` repository. The **architecture** and
**guides** are organized around the **CSSC framework stages** — Acquire,
Catalog, Build, Deploy, and Run — and, within each stage, grouped under two
cross-cutting themes where they apply: **Authenticity and Integrity** and
**Supply Chain Observability**. Reference material and contributing conventions
are kept as cross-cutting areas.

## Structure

| Folder | Purpose |
| ------ | ------- |
| [`architecture/`](architecture/) | Design and architecture docs, organized by stage. |
| [`guides/`](guides/) | How-to and operational guides, organized by stage. |
| [`reference/`](reference/) | Reference material and conventions (cross-cutting). |
| [`contributing/`](contributing/) | Conventions for contributing to this repository. |

## Stages

| Stage | Architecture | Guides |
| ----- | ------------ | ------ |
| **Acquire** | [architecture/acquire/](architecture/acquire/) | [guides/acquire/](guides/acquire/) |
| **Catalog** | [architecture/catalog/](architecture/catalog/) | [guides/catalog/](guides/catalog/) |
| **Build** | [architecture/build/](architecture/build/) | [guides/build/](guides/build/) |
| **Deploy** | [architecture/deploy/](architecture/deploy/) | [guides/deploy/](guides/deploy/) |
| **Run** | [architecture/run/](architecture/run/) | [guides/run/](guides/run/) |

Design docs that span stages live under
[architecture/cross-cutting/](architecture/cross-cutting/).

## Reference

- [Workflow actions and terminology](reference/workflow-actions.md)
- [Image annotations](reference/image-annotations.md)
- [Image attestations](reference/image-attestations.md)

## Contributing

- [Workflow naming conventions](contributing/workflow-naming.md) — how GitHub
  Actions workflows are named and organized in this repository.
