# LatamPay S.A. — Prior Incident Tickets (History)

> SYNTHETIC DATA for workshop use only.

## INC-2022-0417 — Log4j remediation program

- **Date:** 2022-01 to 2022-03
- **Summary:** Following the Log4Shell disclosures, LatamPay ran a fleet-wide program to **remove `log4j-core` from every service** and standardize on **Logback**. Verified via SBOM scanning.
- **Outcome:** Closed. Log4j is confirmed absent from all production services. Any new Log4j-targeting report is **Not Applicable** to the current estate.

## INC-2023-1102 — Apache Struts exploitation attempt on payment-gateway

- **Date:** 2023-11
- **Summary:** WAF blocked crafted OGNL expression payloads aimed at the **payment-gateway** Struts endpoints. No compromise.
- **Lessons:** Struts/OGNL expression-injection weaknesses on the payment-gateway are treated as **high-confidence, high-priority** because the asset is tier-0 and internet-facing. Keep Struts patched aggressively.

## INC-2024-0631 — Legacy SOAP/XML gateway decommission

- **Date:** 2024-06
- **Summary:** The old SOAP/XML gateway (the only XML-parsing internet service) was **decommissioned**. XML external-entity exposure surface was eliminated.
- **Outcome:** No XML SOAP endpoints remain; XXE reports against that product are **Not Applicable**.

## Known-fragile services

- **reconciliation-service** historically deserializes Java objects from the settlement queue; flagged in past reviews as a sensitive code path to watch.
