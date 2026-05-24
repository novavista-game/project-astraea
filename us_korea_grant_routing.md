# US & Korea Public Grant Escrow Routing Specifications

This document defines the algorithmic mapping and purpose-bound escrow routing mechanics for Project Astraea’s public grant distributions across US pilot areas and South Korean municipal zones.

## 1. Agency Matching & Funding Programs

Astraea acts as a decentralized coordination layer matching qualifying households to specific donor program criteria:

### United States Pilot Program
- **Weatherization Assistance Program (WAP)**: Routes funds strictly for roofing degradation and insulation upgrades.
- **Low Income Home Energy Assistance Program (LIHEAP)**: Maps to ventilation, weatherproofing, and heating modifications.
- **USDA Section 504 (Rural Housing Repair Loans & Grants)**: Targeted at elderly citizens (age 62+) in rural regions to remove safety and health hazards.

### South Korea Pilot Program
- **KOICA Official Development Assistance (ODA)**: Public grant allocation targeting low-income, marginalized communities for sanitary infrastructure.
- **Green Climate Fund (GCF-Resilience)**: Directed toward structural reinforcements mitigating flooding, severe heat, and typhoons.

---

## 2. Escrow Release matching Merchant Category Codes (MCC)

To prevent cash diversion, stablecoin liquidity is locked in `AstraeaGrantEscrowVault.sol` and disbursed strictly to authorized merchants upon VLM verification of milestone progress. Merchants are filtered via credit card networks / payment rails using standard ISO 18245 Merchant Category Codes:

| Merchant | Region | Target Upgrade | MCC | Authorization Status |
| :--- | :--- | :--- | :--- | :--- |
| **Lowe's Home Improvement** | US | Roofing, Flooring, Insulation | `5211` (Lumber & Building Materials) | `FUNDS_LOCKED_MCC_COMPLIANT` |
| **The Home Depot** | US | Hardware, Plumbing, Latrines | `5251` (Hardware Stores) | `FUNDS_LOCKED_MCC_COMPLIANT` |
| **The Home Depot** | US | Kitchen Appliances, Range Hoods | `5732` (Electronic Stores/Appliances)| `FUNDS_LOCKED_MCC_COMPLIANT` |
| **LX Hausys** | KR | Windows, Premium Siding, Roofing | `5211` (Lumber & Building Materials) | `FUNDS_LOCKED_MCC_COMPLIANT` |
| **HomePlus** | KR | Plumbing, Pipes, General Hardware | `5311` (General Merchandise) | `FUNDS_LOCKED_MCC_COMPLIANT` |
| **HomePlus** | KR | Kitchen Hoods, Gas Safeties | `5732` (Electronic Stores/Appliances)| `FUNDS_LOCKED_MCC_COMPLIANT` |

---

## 3. Real-Time Escrow State Machine

```mermaid
stateflow
    [*] --> IngestContext : Form & Photo Submitted
    IngestContext --> VlmInference : Geo-Spatial containment passed
    VlmInference --> GrantMatching : HEVI & MCC matching
    GrantMatching --> AgencyAudit : Compliance validations (ZKP signature)
    AgencyAudit --> FundsLocked : Escrow vault lock to MCC code
    FundsLocked --> [*] : Milestone verification releases funds
```
