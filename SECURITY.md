# Security Policy

This document describes the security policy for the **CSSC framework**
repository and the process for reporting a security vulnerability in anything
within this repository, including the reusable workflows and composite actions,
the CSSC Dashboard application images, and the published Helm charts.

- [Reporting a Vulnerability](#reporting-a-vulnerability)
  - [When To Send a Report](#when-to-send-a-report)
  - [What To Include In a Report](#what-to-include-in-a-report)
  - [When Not To Send a Report](#when-not-to-send-a-report)
  - [Security Vulnerability Response](#security-vulnerability-response)
  - [Public Disclosure](#public-disclosure)
- [Supported Versions](#supported-versions)
- [Scope](#scope)
- [Credits](#credits)

## Reporting a Vulnerability

We are extremely grateful for security researchers and users who report
vulnerabilities. All reports are thoroughly investigated by the repository
maintainers.

To make a report, please use the GitHub private vulnerability
disclosure process for this repository:

- [Report a vulnerability](https://github.com/toddysm/cssc-framework/security/advisories/new)

Reports submitted through GitHub Security Advisories are private and visible
only to the maintainers until a fix is published.

### When To Send a Report

Send a report if you think you have found a security vulnerability in:

- the reusable workflows or composite actions in this repository,
- the CSSC Dashboard application or its published container images,
- the published Helm charts, or
- a dependency of any of the above, where the issue is exploitable through this
  repository's artifacts.

### What To Include In a Report

The more details are included in the report, the easier it is for the
maintainers to understand the vulnerability and provide mitigations. Please
include:

- **Short summary** — a single sentence that clearly summarizes the
  vulnerability.
- **Detailed description** — all possible details about the vulnerability:
  affected versions or image digests, the specific source code or workflow,
  environment details, and so on.
- **Proof of Concept (PoC) steps** — detailed steps to reproduce the
  vulnerability, including CLI commands, configuration, and library calls.
- **Impact** — the impact of the vulnerability and who is affected.

Feel free to include anything else that you deem relevant for a better
understanding of the vulnerability.

### When Not To Send a Report

- If you have found a vulnerability in an application that merely *uses* the
  CSSC framework. Instead, contact the maintainers of that application.
- If you are looking for help applying security updates.

### Security Vulnerability Response

Each report will be reviewed and its receipt acknowledged within **3 business
days**. This sets off the security review process.

Any vulnerability information shared with the maintainers stays private and is
only shared on a need-to-know basis as necessary to fix the issue.

We ask that vulnerability reporters act in good faith by not disclosing the
issue to others, and we strive to act in good faith by responding swiftly and by
justly crediting reporters in writing. As the issue moves through triage,
identification, and release, the reporter will be kept informed and may be asked
additional questions.

### Public Disclosure

A public disclosure of a security vulnerability is released alongside the
release or update that fixes it. We try to fully disclose vulnerabilities once a
mitigation is available, and to perform the release and disclosure on a timetable
that works well for users.

Vulnerability disclosures are published in the
[Security Advisories](https://github.com/toddysm/cssc-framework/security/advisories)
section of this repository. Where applicable, a CVE ID will be requested; because
obtaining a CVE ID takes time, the disclosure may be published first and updated
with the CVE ID once it is assigned.

If a reporter would like to be credited, we are happy to do so and will ask how
they would like to be identified.

## Supported Versions

Security fixes are provided for the **latest released version** of the CSSC
framework. Users are encouraged to track the most recent release. Older releases
do not receive security updates unless explicitly noted in a specific advisory.

## Scope

The following are in scope for a security report:

- Reusable workflows (`.github/workflows/_*.yml`) and their caller workflows.
- Composite actions under `.github/actions/`.
- The CSSC Dashboard services and their published container images
  (`ghcr.io/toddysm/apps/cssc-dashboard/*`).
- The published Helm charts (`oci://ghcr.io/toddysm/charts`).

Out of scope:

- Vulnerabilities in upstream base images or third-party dependencies that are
  not exploitable through this repository's artifacts (report those upstream).
- Issues that require a compromised maintainer account or self-hosted runner.

## Credits

This policy is adapted from the security process and policy used by the
[Notary Project](https://github.com/notaryproject) and the
[Helm Community](https://github.com/helm/community).
