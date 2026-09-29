# LatamPay S.A. — Asset Inventory (CMDB Extract)

> SYNTHETIC DATA for workshop use only. LatamPay S.A. is a fictional Latin American digital-payments company. Content is in English for consistency.

## Internet-facing assets (DMZ)

| Asset | Service | Stack | Tier | PCI scope | Notes |
|-------|---------|-------|------|-----------|-------|
| `pay-gw-prod-01/02` | payment-gateway | Apache Struts 2.5.33, Spring Boot 3.2.4, behind Nginx | **tier-0** | Yes | Processes card authorizations. Crown jewel. Uses database credentials for card authorization flows; any credential exposure here is PCI-impacting. |
| `portal-prod-01/02` | customer-portal | React 18 SPA + Spring Boot 3.2.4 backend | tier-1 | Partial | Customer self-service; login, return URL redirect flow, statements. |
| `edge-nginx-01/02` | Nginx 1.25.4 | TLS termination, reverse proxy | tier-1 | Yes | Only DMZ ingress point. |

## Internal assets (private subnets / VPC)

| Asset | Service | Stack | Tier | Notes |
|-------|---------|-------|------|-------|
| `recon-svc-01/02` | reconciliation-service | Spring Boot 3.2.4 | tier-1 | Money-movement reconciliation. Consumes **serialized Java objects** from the settlement queue and exposes internal admin endpoints for replay and settlement operations. |
| `doc-svc-01` | document-service | Spring Boot 3.2.4 | tier-1 | Upload/download of **customer KYC documents (PII)**. |
| `notify-svc-01` | notification-service | Spring Boot 3.2.4 | tier-2 | Sends **outbound webhooks to merchant-supplied callback URLs**; runs in cloud VPC where the metadata endpoint is reachable. |
| `dir-01` | corporate-directory | OpenLDAP / Active Directory | tier-2 | Employee auth; an internal admin tool builds **LDAP filters from form input**. |
| `pg-prod-01/02` | PostgreSQL 14.11 | Primary datastore | tier-1 | All services use PostgreSQL. **No MySQL/MariaDB anywhere.** |
| `redis-prod-01` | Redis 7.2.4 | Cache / sessions | tier-2 | — |

## Explicitly NOT in the estate

- **Log4j** — fully removed during the 2022 remediation program; replaced with **Logback** across all services.
- **MySQL / MariaDB** — never deployed; PostgreSQL only.
- **Legacy SOAP/XML gateway** — decommissioned in 2024; no XML SOAP endpoints remain.
- **WordPress / PHP** — not used anywhere.
