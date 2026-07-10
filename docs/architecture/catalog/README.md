# Catalog — architecture

Design docs for the **Catalog** stage: scanning quarantined images, gating them
on a vulnerability policy, and promoting the ones that pass into `golden/*`.

## Authenticity and Integrity

- [Promote-from-quarantine workflows](promote-from-quarantine-workflows.md) —
  how quarantined images are scanned with Trivy, gated on a severity threshold
  plus CVE exceptions, promoted with a scan-report referrer, and removed from
  quarantine. (The scan-report referrer also serves **Supply Chain
  Observability**.)
- [Promotion override approval](promote-from-quarantine-override-approval.md) —
  the human-in-the-loop approve/deny path for promoting an image that a policy
  would otherwise block.
- [Vulnerability-attestation scan report](promote-from-quarantine-vuln-attestation.md)
  — **(proposed)** replacing the empty scan-report referrer with a content-bearing
  in-toto vulnerability attestation while keeping the `com.cssc.scan.*` summary
  annotations. (Also serves **Supply Chain Observability**.)
