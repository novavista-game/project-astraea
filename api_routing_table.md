# Project Astraea: API Routing Table & Structural Schemas
## B2G Ingress HEVI Scoring & Purpose-Bound Egress Routing

This document defines the structural payloads, endpoint routing mappings, and asynchronous Kafka schemas for Project Astraea’s B2G/G2C grant allocation pipeline.

---

## 1. Client Ingress Gateway Protocol

### `POST /api/v1/ingress/grant-application`
Receives telemetry, anonymized spatial signatures, and before-upgrade images from the field application.

#### Request Headers
*   `Content-Type`: `application/json`
*   `X-Astraea-Device-Sig`: `0x9e8f4...`
*   `X-Astraea-Device-ID`: `dev_uuid_99812487`

#### Request Payload Schema
```json
{
  "application_id": "app_ast_551920_887e",
  "client_timestamp": "2026-05-24T18:54:00Z",
  "anonymized_spatial_data": {
    "h3_index_res12": "8c7a6e1a4db93ff",
    "zkp_spatial_proof": "0x12a9fbc389b09..."
  },
  "image_manifest": [
    {
      "file_hash": "sha256_e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495",
      "capture_target": "ROOF_FACADE"
    },
    {
      "file_hash": "sha256_f8b1c44298fc1c149afbf4c8996fb92427ae41e4649b934ca496",
      "capture_target": "WATER_SAN_SOURCE"
    },
    {
      "file_hash": "sha256_c7a1c44298fc1c149afbf4c8996fb92427ae41e4649b934ca497",
      "capture_target": "LATRINE_INTERIOR"
    },
    {
      "file_hash": "sha256_d9b1c44298fc1c149afbf4c8996fb92427ae41e4649b934ca498",
      "capture_target": "FLOOR_SURFACE"
    }
  ]
}
```

#### Response Payload (`202 Accepted`)
```json
{
  "application_id": "app_ast_551920_887e",
  "status": "QUEUED",
  "hevi_calculation_endpoint": "/api/v1/ingress/hevi-status/app_ast_551920_887e"
}
```

---

## 2. Multimodal VLM HEVI Ingestion Schema

The VLM processes the four uploaded files and outputs a strict JSON payload mapping the **Healthspan Environmental Vulnerability Index (HEVI)**.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AstraeaVlmHeviAssessment",
  "type": "OBJECT",
  "properties": {
    "roofing_condition_metrics": {
      "type": "OBJECT",
      "properties": {
        "primary_material": { "type": "STRING", "enum": ["CANVAS", "WEATHERED_TIMBER", "CORRUGATED_IRON", "CONCRETE_SLAB", "ASBESTOS_SHEET", "UNKNOWN"] },
        "roofing_degradation_index": { "type": "NUMBER", "minimum": 0.0, "maximum": 1.0 },
        "waterproofing_failed": { "type": "BOOLEAN" }
      },
      "required": ["primary_material", "roofing_degradation_index", "waterproofing_failed"]
    },
    "water_sanitation_ingress": {
      "type": "OBJECT",
      "properties": {
        "drinking_water_distance_meters": { "type": "NUMBER" },
        "contamination_source_proximity_meters": { "type": "NUMBER" },
        "water_vulnerability_index": { "type": "NUMBER", "minimum": 0.0, "maximum": 1.0 }
      },
      "required": ["drinking_water_distance_meters", "contamination_source_proximity_meters", "water_vulnerability_index"]
    },
    "sanitary_latrine_metrics": {
      "type": "OBJECT",
      "properties": {
        "latrine_structure_present": { "type": "BOOLEAN" },
        "septic_tank_integrated": { "type": "BOOLEAN" },
        "sanitation_degradation_index": { "type": "NUMBER", "minimum": 0.0, "maximum": 1.0 }
      },
      "required": ["latrine_structure_present", "septic_tank_integrated", "sanitation_degradation_index"]
    },
    "floor_composition_score": {
      "type": "OBJECT",
      "properties": {
        "floor_material": { "type": "STRING", "enum": ["DIRT", "CONCRETE", "TILE", "RAISED_WOOD", "UNKNOWN"] },
        "pathogen_exposure_risk_index": { "type": "NUMBER", "minimum": 0.0, "maximum": 1.0 }
      },
      "required": ["floor_material", "pathogen_exposure_risk_index"]
    }
  },
  "required": ["roofing_condition_metrics", "water_sanitation_ingress", "sanitary_latrine_metrics", "floor_composition_score"]
}
```

---

## 3. Public Grant Escrow Smart Contract Interface

The on-chain matching registry tracks project statuses and disburses funds exclusively to whitelisted local material vendors.

### `GrantEscrow.sol` (EVM Interface)
```solidity
interface IGrantEscrow {
    enum MilestoneStatus { PENDING, STAGE1_RELEASED, COMPLETED, CANCELLED }

    struct GrantProject {
        uint256 totalAllocated;
        uint256 amountReleased;
        address residentAddress;
        address vendorAddress;
        MilestoneStatus status;
        bool isRegistered;
    }

    event GrantDeposited(address indexed donor, uint256 amount);
    event ProjectRegistered(uint256 indexed projectId, address indexed resident, address indexed vendor, uint256 allocation);
    event Milestone1Disbursed(uint256 indexed projectId, address indexed vendor, uint256 amount);
    event Milestone2Disbursed(uint256 indexed projectId, address indexed vendor, uint256 amount);

    function depositGrant(uint256 amount) external;
    
    function registerProject(
        uint256 projectId,
        address resident,
        address vendor,
        uint256 totalCost
    ) external;

    function releaseMilestone1(uint256 projectId) external;

    function releaseMilestone2(uint256 projectId) external;
}
```

---

## 4. B2G Egress: Automated Transparency Impact Report

Once final VLM checks verify completion, this payload is automatically pushed via REST API to the donor institution's monitoring dashboard.

#### `GET /api/v1/egress/transparency-report?project_id=1001`
*   **Authorization**: Bearer JWT (Grant Provider Token)

##### Response Payload (`200 OK`)
```json
{
  "project_id": 1001,
  "escrow_contract_address": "0x7a5b3f11c828da0182f0c19a9bc0d12ab4582910",
  "verification_timestamp": "2026-05-24T18:54:21Z",
  "donor_transparency_metrics": {
    "pre_upgrade_bdi": 0.78,
    "post_upgrade_bdi": 0.18,
    "hevi_improvement_score": 92.5,
    "infection_risk_reduction_percentage": 78.4,
    "funds_released_to_vendor_usdc": 1500.0,
    "settlement_transaction_hash": "0x8e2b1001fa28f090b82f0c19a9bc0d12ab89c201d84a7e"
  },
  "validation_meta": {
    "vlm_verification_passed": true,
    "anonymized_h3_index": "8c7a6e1a4db93ff"
  }
}
```
This routing schema enforces zero data leaks of raw personal coordinates while guaranteeing maximum auditability to donor agencies.
