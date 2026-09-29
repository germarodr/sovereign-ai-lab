# LatamPay S.A. — Network Trust Zones

> SYNTHETIC DATA for workshop use only.

## Zones

| Zone | Reachable from | Contains |
|------|----------------|----------|
| **DMZ** | Public internet | Nginx edge, payment-gateway, customer-portal |
| **App (private)** | DMZ + internal | reconciliation-service, document-service |
| **Cloud VPC** | Internal only | notification-service (egress to internet via NAT) |
| **Corp** | Internal only | corporate-directory (LDAP/AD), employee admin tools |
| **Data** | App + Cloud VPC only | PostgreSQL, Redis |

## Notes that affect blast radius

- The **payment-gateway** and **customer-portal** are the only services directly reachable from the internet.
- **notification-service** runs in the **Cloud VPC**; the cloud **metadata endpoint (169.254.169.254)** is reachable from that subnet, so any outbound-request weakness there can pivot to cloud credentials.
- **document-service** is internal but stores **customer PII (KYC)**; a read weakness there is a data-exposure risk even though it is not internet-facing.
- The **corporate-directory** is reachable only from the Corp zone; an internal admin tool there constructs LDAP queries from user input.
- The legacy SOAP/XML gateway that previously sat in the DMZ was **decommissioned in 2024**; no XML SOAP endpoints remain in any zone.
