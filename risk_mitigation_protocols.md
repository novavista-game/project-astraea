# Project Astraea: Risk Mitigation Protocols & Systems Security
## Multi-Dimensional Threat Modeling & Public Grant Safety

This document establishes the risk mitigation framework for the B2G/G2C public grant allocation model of **Project Astraea**, analyzing threats across four dimensions (Time, Space, Causality, Hierarchy).

---

## 1. Primary Operational Risks (B2G/G2C Context)

### A. Resident Moral Hazard & Cash Diversion
*   **Threat**: Diversion of humanitarian funds by beneficiaries if cash grants are paid directly. Beneficiaries under financial stress face strong incentives to misallocate funds toward immediate consumption, alcohol, or non-essential goods.
*   **Systemic Countermeasure**: **Purpose-Bound Escrow Mapping**. Total elimination of direct cash transfers to beneficiaries. Funds remain locked in `GrantEscrow.sol` and are paid directly to verified, whitelisted local hardware materials merchants.

### B. Education & Trust Deficits (Under-Adoption)
*   **Threat**: Lack of local resident participation due to digital literacy barriers, skepticism regarding blockchain validation, or distrust of external survey efforts.
*   **Systemic Countermeasure**: **Zero User Cost & Local Trust Guilds**. The service is completely free to residents (zero user fee). Survey operations are conducted by local community trust members (Occupancy Guilds) using simple edge-app interfaces.

---

## 2. Multi-Dimensional Risk Analysis Matrix

```
                  [Hierarchy: Local Mediation & Whitelist Verification]
                                       |
                                       |
   [Space: zk-SNARK H3 Anonymity] <----+--------> [Time: Milestone Split Payouts]
                                       |
                                       |
                   [Causality: Post-Upgrade VLM Verification (>=85%)]
```

### A. The Time Dimension: Milestone Split Payouts
*   **Threat**: Contractors or suppliers taking 100% of materials funds and failing to execute the physical repairs.
*   **Mitigation**: **40/60 Milestone Dispersal**. Escrow contracts disburse 40% upon verified ordering. The remaining 60% balance is locked in time and space until construction completes.

### B. The Space Dimension: Privacy Leakage
*   **Threat**: Public ledger exposing exact locations of vulnerable residents, making them targets for land-grab syndicates or slum-lords.
*   **Mitigation**: **ZK-SNARK Spatial Index Obfuscation**. Exact coordinates are checked at the edge; only coarse, zk-proven H3 indices map to the L2 ledger.

### C. The Causality Dimension: Collateral Fraud & Double Claims
*   **Threat**: Suppliers colluding with residents to upload old photos or photos of another house to claim the 60% final release without building anything.
*   **Mitigation**: **Before/After Pixel-Difference Verification (Threshold 85%)**.
    *   The VLM compares the "before" and "after" images using neural difference mapping.
    *   It identifies specific material improvements (e.g. mud floor to concrete floor, toxic asbestos roofing to concrete tiling).
    *   It outputs a quantitative improvement score. The remaining 60% is blocked if the score is `< 85%`.

### D. The Hierarchy Dimension: Vendor Cartels
*   **Threat**: Local material suppliers inflating prices or delivering substandard materials.
*   **Mitigation**: **Governance-Enforced Vendor Whitelisting**. Only registered local hardware vendors with audited price indexes can participate in direct payouts. Substandard deliveries result in instant whitelist removal.
