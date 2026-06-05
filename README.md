# Containers and Cloud-Native Secure Supply Chain Framework Implementation and Demo Project

[![GitHub issues](https://img.shields.io/github/issues-raw/toddysm/cssc-framework)](https://github.com/toddysm/cssc-framework/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr-raw/toddysm/cssc-framework)](https://github.com/toddysm/cssc-framework/pulls)
[![License](https://img.shields.io/github/license/toddysm/cssc-framework)](LICENSE)

Containers Secure Supply Chain (CSSC) Framework implementation — a hands-on
demonstration repository that shows how to put the practices from the
[Containers Secure Supply Chain framework](https://aka.ms/cssc/framework) and
the [Custos project](https://github.com/toddysm/custos) into action.

## Overview

Securing a container supply chain is not a single step — it spans acquiring
upstream artifacts, building on trusted bases, scanning and patching, signing,
generating SBOMs, and enforcing policy at deploy time. This repository brings
those stages together as working, runnable examples so you can see how each
piece fits.

It is intended as a **demonstration and reference**, not a production system.
The samples are deliberately small so the security mechanics stay front and
center.

## What's here today

The repository currently demonstrates the supply chain stages using three
independent sample applications, each built on a base image that is mirrored
from an upstream registry into a controlled namespace before use:

| App | Language | Build tool | Folder |
| --- | -------- | ---------- | ------ |
| Python web app | Python | pip | [`apps/python-app/`](apps/python-app/) |
| Node.js web app | Node.js | npm | [`apps/nodejs-app/`](apps/nodejs-app/) |
| Java web app | Java | Gradle | [`apps/java-app/`](apps/java-app/) |

Supporting capabilities already in place include:

- **Base image mirroring** — GitHub Actions workflows that copy upstream images
  into a `quarantine/` namespace in GHCR, refreshing only when the upstream
  digest changes. See the
  [workflow naming conventions](docs/contributing/workflow-naming.md).

Planned supply chain building blocks — acquire, scan, patch, sign, and
SBOM-generation — will be added as the demonstration grows.

## What's coming next

This repository will grow beyond container apps to cover **AI-related
artifacts** — models, datasets, and other ML supply chain components — and
demonstrate how to secure them with the same supply chain principles:
provenance, scanning, signing, SBOMs/AI-BOMs, and policy enforcement.

## Relationship to the CSSC framework and Custos

- The **[CSSC framework](https://aka.ms/cssc/framework)** defines the stages and
  practices for securing a container supply chain. This repository provides
  concrete, runnable examples of those stages.
- The **[Custos project](https://github.com/toddysm/custos)** is the broader
  effort this repository supports; the samples here demonstrate steps and
  artifacts from that work.

## Repository layout

| Path | Purpose |
| ---- | ------- |
| [`apps/`](apps/) | Sample applications demonstrating the supply chain stages. |
| [`docs/`](docs/) | Detailed documentation, organized by topic. |
| [`.github/workflows/`](.github/workflows/) | Mirror and automation workflows. |

## Documentation

Detailed documentation lives in [`docs/`](docs/README.md), organized by topic:

- [Architecture](docs/architecture/) — design and architecture documentation.
- [Guides](docs/guides/) — how-to and operational guides.
- [Reference](docs/reference/) — reference material and conventions.
- [Contributing](docs/contributing/) — conventions for contributing, including
  [workflow naming](docs/contributing/workflow-naming.md).

## Contributing

See [`MAINTAINERS`](MAINTAINERS) and the
[contributing docs](docs/contributing/) for conventions used in this
repository.

## License

Licensed under the [Apache License 2.0](LICENSE).
