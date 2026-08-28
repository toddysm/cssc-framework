# Project State

Capability inventory for the CSSC (Cloud-native Supply Chain Security) framework,
maintained by My Feature Engineer. This file tracks *what the project has and is
building*; the GitHub Project board (when one exists) tracks *transient work in
flight*. Rows move to **Implemented** only once a capability's required work
(including its user docs) has landed on `main`.

> NOTE: This inventory was **bootstrapped** from existing GitHub issues/PRs and a
> code scan on 2026-08-25. Rows are backed by the linked issues/PRs; capability
> groupings and `Landed` months are derived from that history and refined via
> review.
>
> The account's only GitHub Project ("CNSR Roadmap Project", #3) tracks a
> separate Azure Container Registry roadmap and the agent-tooling backlog — its
> items do not correspond to this repository's issues. This repo therefore runs
> **issues-only**: In progress vs Planned below is classified from issue/PR
> state, not a board Status field.

Capabilities are grouped by the CSSC framework stages the repo is organized
around: **Acquire, Build, Catalog, Deploy, Run**, and the cross-cutting
**Observability** (supply-chain graph) and CI concerns.

## Implemented

| Capability | Feature slug | Tracking issue | PRD doc | Docs | Landed |
| --- | --- | --- | --- | --- | --- |
| Acquire: sync/mirror images from upstream registries (DockerHub) into quarantine | mirror-image | [#1](https://github.com/toddysm/cssc-framework/issues/1), [#51](https://github.com/toddysm/cssc-framework/issues/51), [#55](https://github.com/toddysm/cssc-framework/issues/55) | — | [docs/architecture/acquire](https://github.com/toddysm/cssc-framework/tree/main/docs/architecture/acquire) | 2026-06 |
| Acquire: mirror Docker Hardened Images + SBOM-based scanning into hardened namespaces | mirror-hardened | [#50](https://github.com/toddysm/cssc-framework/issues/50), [#52](https://github.com/toddysm/cssc-framework/issues/52), [#54](https://github.com/toddysm/cssc-framework/issues/54) | — | — | 2026-06 |
| Acquire: acquisition-provenance OCI referrer attached on mirror | acquisition-provenance | [#140](https://github.com/toddysm/cssc-framework/issues/140), [#141](https://github.com/toddysm/cssc-framework/issues/141), [#142](https://github.com/toddysm/cssc-framework/issues/142), [#143](https://github.com/toddysm/cssc-framework/issues/143) | — | [reference/acquisition-provenance.md](https://github.com/toddysm/cssc-framework/blob/main/docs/reference/acquisition-provenance.md) | 2026-07 |
| Acquire: mirror-history artifact (skip re-syncing already-mirrored digests) | mirror-history | [#158](https://github.com/toddysm/cssc-framework/issues/158), [#159](https://github.com/toddysm/cssc-framework/issues/159), [#160](https://github.com/toddysm/cssc-framework/issues/160), [#161](https://github.com/toddysm/cssc-framework/issues/161), [#195](https://github.com/toddysm/cssc-framework/issues/195) | — | [reference/mirror-history.md](https://github.com/toddysm/cssc-framework/blob/main/docs/reference/mirror-history.md) | 2026-08 |
| Catalog: scan-and-promote workflows (quarantine → golden vulnerability gate) | scan-and-promote | [#41](https://github.com/toddysm/cssc-framework/issues/41), [#42](https://github.com/toddysm/cssc-framework/issues/42), [#43](https://github.com/toddysm/cssc-framework/issues/43), [#44](https://github.com/toddysm/cssc-framework/issues/44), [#45](https://github.com/toddysm/cssc-framework/issues/45), [#56](https://github.com/toddysm/cssc-framework/issues/56) | — | [docs/architecture/catalog](https://github.com/toddysm/cssc-framework/tree/main/docs/architecture/catalog) | 2026-06 |
| Catalog: human-in-the-loop override approval for blocked images + Slack notify | promote-override | [#64](https://github.com/toddysm/cssc-framework/issues/64), [#65](https://github.com/toddysm/cssc-framework/issues/65)–[#71](https://github.com/toddysm/cssc-framework/issues/71), [#74](https://github.com/toddysm/cssc-framework/issues/74) | — | [promote-from-quarantine-override-approval.md](https://github.com/toddysm/cssc-framework/blob/main/docs/architecture/catalog/promote-from-quarantine-override-approval.md) | 2026-06 |
| Catalog: vulnerability-attestation scan-report referrer + end-to-end wiring | vuln-attestation | [#146](https://github.com/toddysm/cssc-framework/issues/146) (PR [#152](https://github.com/toddysm/cssc-framework/pull/152)) | — | [image-attestations.md](https://github.com/toddysm/cssc-framework/blob/main/docs/reference/image-attestations.md) | 2026-07 |
| Build: OCI multi-arch images with manifest + index annotations | build-multiarch | [#108](https://github.com/toddysm/cssc-framework/issues/108) | — | [docs/architecture/build](https://github.com/toddysm/cssc-framework/tree/main/docs/architecture/build) | 2026-07 |
| Build: SBOM + SLSA provenance published as OCI 1.1 referrers | build-attestations | [#109](https://github.com/toddysm/cssc-framework/issues/109), [#110](https://github.com/toddysm/cssc-framework/issues/110), [#111](https://github.com/toddysm/cssc-framework/issues/111), [#115](https://github.com/toddysm/cssc-framework/issues/115), [#116](https://github.com/toddysm/cssc-framework/issues/116), [#117](https://github.com/toddysm/cssc-framework/issues/117) | — | [image-attestations.md](https://github.com/toddysm/cssc-framework/blob/main/docs/reference/image-attestations.md) | 2026-07 |
| Build: semantic-version tagging + tag/lineage annotations | semver-tagging | [#123](https://github.com/toddysm/cssc-framework/issues/123), [#124](https://github.com/toddysm/cssc-framework/issues/124), [#125](https://github.com/toddysm/cssc-framework/issues/125), [#126](https://github.com/toddysm/cssc-framework/issues/126) | — | [image-annotations.md](https://github.com/toddysm/cssc-framework/blob/main/docs/reference/image-annotations.md) | 2026-07 |
| Build: security-policy + vulnerability-reporting annotations | security-policy | [#134](https://github.com/toddysm/cssc-framework/issues/134), [#136](https://github.com/toddysm/cssc-framework/issues/136) | — | [SECURITY.md](https://github.com/toddysm/cssc-framework/blob/main/SECURITY.md) | 2026-07 |
| Cross-cutting: automatic CI-failure issue filing (workflow_run monitor) + Slack | ci-failure-notifications | [#80](https://github.com/toddysm/cssc-framework/issues/80), [#81](https://github.com/toddysm/cssc-framework/issues/81), [#82](https://github.com/toddysm/cssc-framework/issues/82), [#83](https://github.com/toddysm/cssc-framework/issues/83), [#84](https://github.com/toddysm/cssc-framework/issues/84), [#85](https://github.com/toddysm/cssc-framework/issues/85) | — | [cross-cutting/ci-failure-notifications.md](https://github.com/toddysm/cssc-framework/blob/main/docs/architecture/cross-cutting/ci-failure-notifications.md) | 2026-06 |
| Run: CSSC Dashboard demo app (dashboard-web, issues-service, packages-service, cssc_common) + Helm charts + kind orchestration | cssc-dashboard | [#98](https://github.com/toddysm/cssc-framework/issues/98), [#91](https://github.com/toddysm/cssc-framework/issues/91)–[#97](https://github.com/toddysm/cssc-framework/issues/97), [#101](https://github.com/toddysm/cssc-framework/issues/101)–[#106](https://github.com/toddysm/cssc-framework/issues/106) | — | [run/cssc-dashboard.md](https://github.com/toddysm/cssc-framework/blob/main/docs/architecture/run/cssc-dashboard.md) | 2026-07 |
| Observability: supply-chain graph — Phases 1–6 (schema/files, indexer + LadybugDB, acquire/catalog producers, provenance queries + CLI, build producers + base lineage, graph-service + dashboard views) | supply-chain-graph | [#170](https://github.com/toddysm/cssc-framework/issues/170)–[#175](https://github.com/toddysm/cssc-framework/issues/175) | — | [observability/supply-chain-graph.md](https://github.com/toddysm/cssc-framework/blob/main/docs/architecture/observability/supply-chain-graph.md) | 2026-08 |
| Observability: graph events for all artifacts + deletions; referrers (REFERS_TO) in queries/visualization | graph-referrers | [#199](https://github.com/toddysm/cssc-framework/issues/199), [#205](https://github.com/toddysm/cssc-framework/issues/205), [#203](https://github.com/toddysm/cssc-framework/issues/203), [#204](https://github.com/toddysm/cssc-framework/issues/204) | — | [observability/supply-chain-graph.md](https://github.com/toddysm/cssc-framework/blob/main/docs/architecture/observability/supply-chain-graph.md) | 2026-08 |
| Observability: model multi-arch index ↔ per-architecture child manifest relationship | multiarch-index-platform | [#216](https://github.com/toddysm/cssc-framework/issues/216) | — | — | 2026-08 |
| Catalog: promotion + quarantine cleanup includes all referrers (OCI 1.0 + 1.1) | promote-referrers | [#198](https://github.com/toddysm/cssc-framework/issues/198) | — | — | 2026-08 |
| Early CI supply-chain tasks (Trivy scan, sign, SBOM, provenance, lifecycle, signature/vuln/lifecycle verification, Copa patching) | ci-tasks | [#2](https://github.com/toddysm/cssc-framework/issues/2)–[#14](https://github.com/toddysm/cssc-framework/issues/14), [#22](https://github.com/toddysm/cssc-framework/issues/22) | — | — | 2023 |

> NOTE: `Landed` values are the month the capability's representative issue was
> closed / its PR merged. Several capabilities predate agent-managed tracking,
> so `PRD doc` is `—`.

## In progress

| Capability | Feature slug | Tracking issue | PRD doc | Docs |
| --- | --- | --- | --- | --- |
| Observability: supply-chain graph — overall implementation epic | supply-chain-graph | [#177](https://github.com/toddysm/cssc-framework/issues/177) | — | — |
| Observability: roll up per-platform child referrers/attestations to the index in graph queries/views (PR [#221](https://github.com/toddysm/cssc-framework/pull/221) open on `feat/rollup-platform-referrers`, CI green, awaiting review) | rollup-platform-referrers | [#217](https://github.com/toddysm/cssc-framework/issues/217) | — | — |
| Observability: provenance timeline view (digest-level, dated, per-family) + sub-items | provenance-timeline | [#210](https://github.com/toddysm/cssc-framework/issues/210), [#211](https://github.com/toddysm/cssc-framework/issues/211)–[#215](https://github.com/toddysm/cssc-framework/issues/215) | — | — |
| Observability: represent/present multi-arch (index) + per-architecture manifests in the graph (design) | multiarch-graph-present | [#218](https://github.com/toddysm/cssc-framework/issues/218) | — | — |
| Observability: stage ImageIndexObserved events from build/app-image workflows | image-index-observed | [#220](https://github.com/toddysm/cssc-framework/issues/220) | — | — |
| Acquire: mirror-history end-to-end validation + persist to skip re-sync | mirror-history-validation | [#157](https://github.com/toddysm/cssc-framework/issues/157), [#163](https://github.com/toddysm/cssc-framework/issues/163) | — | — |

## Planned

| Capability | Feature slug | Tracking issue |
| --- | --- | --- |
| Observability: define file-backed artifact discovery and lineage requirements | graph-discovery-reqs | [#168](https://github.com/toddysm/cssc-framework/issues/168) |

## Deferred / Won't do

| Capability | Feature slug | Tracking issue | Reason |
| --- | --- | --- | --- |
| Observability: supply-chain graph — Phase 7 (SBOM/scan ingestion + CVE queries) | supply-chain-graph-phase7 | [#176](https://github.com/toddysm/cssc-framework/issues/176) | Explicitly deferred to a later phase. |
| Observability: index image flow with Kùzu (embedded graph store) | graph-kuzu | [#145](https://github.com/toddysm/cssc-framework/issues/145) | Superseded — Kùzu is archived; the implemented graph engine is **LadybugDB** (its maintained successor). See [supply-chain-graph.md](https://github.com/toddysm/cssc-framework/blob/main/docs/architecture/observability/supply-chain-graph.md). |

## Known gaps & debt

| Gap | Notes |
| --- | --- |
| No PRD/EDD documents on record for pre-agent capabilities | Most Implemented rows predate agent-managed planning; `PRD doc` column is `—`. New features should author a PRD+EDD in the repo (My Feature Engineer creates the requirements folder lazily on the first plan). |
| Vuln-attestation wiring issues open despite merged code | [#147](https://github.com/toddysm/cssc-framework/issues/147)–[#151](https://github.com/toddysm/cssc-framework/issues/151) remain **open**, but PR [#152](https://github.com/toddysm/cssc-framework/pull/152) (merged 2026-07-10) appears to have implemented the end-to-end wiring (scan actions emit cosign-vuln predicates; both reusable promote workflows pass `attestation-path` to `attach-scan-report`). Verify and close the stale sub-issues. |
| Project board does not track this repo | The only Project ("CNSR Roadmap Project" #3) tracks a separate ACR roadmap; this repo runs issues-only. Consider a dedicated Project if board-driven Status is wanted. |
| Open promotion-pending gate | [#222](https://github.com/toddysm/cssc-framework/issues/222) (ghcr.io/toddysm/quarantine/python:3.14-slim) is an open human-in-the-loop promotion gate, not a feature — awaiting reviewer action. |
| Bootstrap inference | This inventory was generated from issue/PR history and a code scan; treat capability groupings as a starting point pending a human read. |
