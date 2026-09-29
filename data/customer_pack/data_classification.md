# LatamPay S.A. — Data Classification & Compliance Context

> SYNTHETIC DATA for workshop use only.

## Data classification

| Class | Examples | Where it lives |
|-------|----------|----------------|
| **Restricted** | Cardholder data (PAN), card auth flows | payment-gateway, PostgreSQL (PCI scope) |
| **Confidential (PII)** | KYC documents, customer identity data | document-service, PostgreSQL |
| **Internal** | Reconciliation/settlement records | reconciliation-service, PostgreSQL |
| **Public** | Marketing content | customer-portal static assets |

## Asset tiers

| Tier | Meaning | Assets |
|------|---------|--------|
| **tier-0** | Mission-critical, cardholder data, max scrutiny | payment-gateway |
| **tier-1** | Important; customer data or money movement | customer-portal, reconciliation-service, document-service, PostgreSQL |
| **tier-2** | Supporting internal services | notification-service, corporate-directory, Redis |
| **tier-3** | Non-prod / sandbox | dev sandboxes |

## Compliance scope

- **PCI-DSS:** in scope for payment-gateway and any system that stores/processes/transmits cardholder data.
- **SOC 2 (Type II):** organization-wide controls; remediation timeliness is audited against the SLA policy.
- **Local data-protection law (LatAm jurisdictions LatamPay operates in):** customer PII (KYC) handling requires breach notification; weaknesses exposing PII escalate to the Data Protection Officer.
