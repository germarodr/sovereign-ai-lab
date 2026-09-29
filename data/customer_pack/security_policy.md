# LatamPay S.A. — Security Policy & Remediation SLAs

> SYNTHETIC DATA for workshop use only.

## Patch / remediation SLAs

| Asset exposure | Severity | Remediation SLA |
|----------------|----------|-----------------|
| Internet-facing (DMZ) | Critical / High | **24 hours** |
| Internet-facing (DMZ) | Medium | 7 days |
| Internal | Critical / High | **30 days** |
| Internal | Medium / Low | 90 days |

- **Tier-0 assets** (payment-gateway) follow the internet-facing SLA **regardless of how the weakness is reached**, and any confirmed exploitable weakness on tier-0 triggers **immediate incident escalation** to the on-call security lead.
- Assets **in PCI-DSS scope** require a remediation ticket and a compensating control documented within **4 hours** of confirmation.

## Escalation rules

1. Any exploitable weakness on a **tier-0** or **PCI-scope** asset → page the security on-call immediately; open a Sev-1.
2. Weaknesses exposing **customer PII** (e.g., KYC documents) → escalate to the Data Protection Officer; treat as **High** minimum.
3. Weaknesses reachable from the **internet** are prioritized one level above the same weakness on an internal-only asset.
4. Any weakness that can expose cloud instance metadata or cloud credentials is treated as **Critical**, even if the vulnerable service is internal-only.

## Applicability rule

A reported weakness is **only actionable if the affected software/component is present in the LatamPay estate** (see asset inventory and SBOM). Findings against software LatamPay does not run are marked **Not Applicable** and closed, with a note.
