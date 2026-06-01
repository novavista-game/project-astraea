import json
import math
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AstraeaPipeline")

class AdminGatewayAgent:
    """
    Agent 1: Admin_Gateway_Agent
    Listens to KOICA/GCF Webhook triggers for application approvals.
    """
    def __init__(self, oracle_agent):
        self.oracle = oracle_agent

    def receive_approval_webhook(self, payload):
        app_id = payload.get("application_id")
        status = payload.get("status")
        grant_amount = payload.get("allocated_grant_usd")
        gps = payload.get("beneficiary_gps")
        region = payload.get("region")

        logger.info(f"[Admin_Gateway] Webhook received for Application #{app_id} (Status: {status})")
        
        if status == "Approved":
            # Initiate Phase 1: Lock-up
            logger.info(f"[Admin_Gateway] Triggering Phase 1 Lock-up for Application #{app_id}")
            lock_success, tx_hash = self.oracle.lock_funds(app_id, grant_amount, gps, region)
            return lock_success, tx_hash
        else:
            logger.warning(f"[Admin_Gateway] Application #{app_id} is not in 'Approved' state. Ignoring.")
            return False, None


class SmartContractOracle:
    """
    Agent 2: Smart_Contract_Oracle
    Interfaces with Web3 Smart Contracts (or simulated Ledger API) to control funds locks/releases.
    """
    def __init__(self):
        # Simulated database of escrow accounts
        self.escrow_db = {}
        self.contract_address = "0x7a5b3f11c828da0182f0c19a9bc0d12ab4582910"

    def lock_funds(self, app_id, amount, gps, region):
        tx_hash = f"0xlock_{app_id}_{hash(str(gps)) % 1000000:06x}"
        self.escrow_db[app_id] = {
            "amount": amount,
            "gps": gps,
            "region": region,
            "status": "LOCKED",
            "locked_timestamp": datetime.now(timezone.utc).isoformat(),
            "tx_hash": tx_hash,
            "vendor_assigned": None,
            "red_flag": False,
            "red_flag_reason": None
        }
        logger.info(f"[Smart_Contract_Oracle] Funds locked. {amount} USDC secured in vault {self.contract_address}. Tx: {tx_hash}")
        return True, tx_hash

    def release_funds(self, app_id, vendor_id, vendor_bank_acc):
        account = self.escrow_db.get(app_id)
        if not account:
            logger.error(f"[Smart_Contract_Oracle] Escrow account not found for Application #{app_id}")
            return False

        if account["status"] != "LOCKED":
            logger.error(f"[Smart_Contract_Oracle] Cannot release funds. Current status: {account['status']}")
            return False

        # Release to Vendor bank account
        account["status"] = "RELEASED"
        account["settled_timestamp"] = datetime.now(timezone.utc).isoformat()
        account["payout_vendor"] = vendor_id
        account["payout_account"] = vendor_bank_acc
        account["release_tx_hash"] = f"0xrelease_{app_id}_{hash(vendor_bank_acc) % 1000000:06x}"

        logger.info(f"[Smart_Contract_Oracle] Payout completed: {account['amount']} USDC transferred to Vendor #{vendor_id} ({vendor_bank_acc}). Status: Settled. Tx: {account['release_tx_hash']}")
        return True

    def raise_red_flag(self, app_id, reason):
        account = self.escrow_db.get(app_id)
        if account:
            account["red_flag"] = True
            account["red_flag_reason"] = reason
            account["status"] = "SUSPENDED"
            logger.warning(f"[Smart_Contract_Oracle] RED FLAG RAISED for Application #{app_id}. Reason: {reason}. Escrow suspended.")
            return True
        return False

    def get_account_status(self, app_id):
        return self.escrow_db.get(app_id)


class VendorDispatchAgent:
    """
    Agent 3: Vendor_Dispatch_Agent
    Matches beneficiaries to the closest whitelisted vendors and dispatches orders.
    """
    def __init__(self, oracle_agent):
        self.oracle = oracle_agent
        # Whitelisted vendor database categorized by region
        self.vendors_db = {
            "South Korea": [
                {"id": "KR_LX_01", "name": "LX Hausys Songpa Branch", "gps": (37.514, 127.123), "bank": "KB_Bank_394-01-2093"},
                {"id": "KR_HP_02", "name": "HomePlus Songpa Store", "gps": (37.511, 127.105), "bank": "Shinhan_Bank_110-384-93"}
            ],
            "Kenya": [
                {"id": "KE_KT_01", "name": "Kibera Timber Depot", "gps": (-1.312, 36.788), "bank": "M-Pesa_Till_298492"},
                {"id": "KE_NH_02", "name": "Nairobi Hardware Supplies", "gps": (-1.309, 36.812), "bank": "Equity_Bank_019284092"}
            ],
            "USA": [
                {"id": "US_HD_01", "name": "The Home Depot Dallas East", "gps": (32.812, -96.721), "bank": "Wells_Fargo_8390192"},
                {"id": "US_LW_02", "name": "Lowe's Dallas Central", "gps": (32.834, -96.755), "bank": "Chase_Bank_4920193"}
            ]
        }

    def _calculate_distance(self, p1, p2):
        # Haversine distance formula to calculate distance between two coordinates
        lat1, lon1 = p1
        lat2, lon2 = p2
        R = 6371.0 # Earth's radius in km

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def match_and_dispatch(self, app_id):
        account = self.oracle.get_account_status(app_id)
        if not account or account["status"] != "LOCKED":
            logger.error(f"[Vendor_Dispatch] Cannot dispatch for Application #{app_id}. Invalid account state.")
            return False

        beneficiary_gps = account["gps"]
        region = account["region"]
        regional_vendors = self.vendors_db.get(region, [])

        if not regional_vendors:
            logger.error(f"[Vendor_Dispatch] No whitelisted vendors found in region: {region}")
            self.oracle.raise_red_flag(app_id, f"No vendors available in region {region}")
            return False

        # Find closest vendor
        closest_vendor = min(regional_vendors, key=lambda v: self._calculate_distance(beneficiary_gps, v["gps"]))
        distance = self._calculate_distance(beneficiary_gps, closest_vendor["gps"])

        logger.info(f"[Vendor_Dispatch] Closest Vendor matched: {closest_vendor['name']} (Vendor ID: {closest_vendor['id']}) located {distance:.2f} km away.")
        
        # Assign vendor to escrow registry
        account["vendor_assigned"] = closest_vendor
        account["system_state"] = "Pending Delivery"

        # Dispatch simulated notification payload to the vendor portal
        notification_payload = {
            "notification_type": "DELIVERY_DISPATCH",
            "application_id": app_id,
            "vendor_id": closest_vendor["id"],
            "beneficiary_info": f"Astraea Beneficiary #{app_id}",
            "material_standard": "Resilience Structural Material (Grade A)",
            "destination_gps": beneficiary_gps
        }
        
        logger.info(f"[Vendor_Dispatch] Dispatched delivery instructions to Vendor portal: {json.dumps(notification_payload)}")
        return True

    def trigger_timeout_check(self, app_id, days_elapsed):
        """
        Exception Handling Rule: Warn vendor if 7 days elapsed without upload.
        """
        account = self.oracle.get_account_status(app_id)
        if account and account.get("system_state") == "Pending Delivery" and days_elapsed >= 7:
            vendor = account.get("vendor_assigned")
            logger.warning(f"[Vendor_Dispatch] EXCEPTION DETECTED: Vendor {vendor['id']} has not uploaded delivery proof for {days_elapsed} days. Issuing warning alert.")
            return True
        return False


class ProofVerificationAgent:
    """
    Agent 4: Proof_Verification_Agent
    Validates delivery proofs (Photos + QR scans) using multimodal VLM simulation.
    """
    def __init__(self, oracle_agent):
        self.oracle = oracle_agent

    def verify_delivery_proof(self, app_id, proof_payload):
        """
        Phase 3: Verification & Release
        Validates QR code match and visual integrity of the delivery photo.
        """
        account = self.oracle.get_account_status(app_id)
        if not account or account.get("system_state") != "Pending Delivery":
            logger.error(f"[Proof_Verification] Application #{app_id} is not pending delivery. Verification aborted.")
            return False

        qr_scan_data = proof_payload.get("qr_data")
        photo_quality = proof_payload.get("photo_quality") # Simulating VLM feedback (HIGH/LOW)
        vendor_id = proof_payload.get("vendor_id")

        logger.info(f"[Proof_Verification] Receiving delivery proof for Application #{app_id} from Vendor {vendor_id}...")

        # 1. QR code validation
        if qr_scan_data != f"AST-QR-{app_id}":
            err_msg = "QR Code mismatch: The beneficiary QR does not match the application ID."
            logger.error(f"[Proof_Verification] Verification Failed. {err_msg}")
            self.oracle.raise_red_flag(app_id, err_msg)
            return False

        # 2. VLM visual integrity check
        if photo_quality != "HIGH":
            err_msg = "VLM validation failed: Rusted iron roof/dirt floor detected instead of upgraded materials."
            logger.error(f"[Proof_Verification] Verification Failed. {err_msg}")
            self.oracle.raise_red_flag(app_id, err_msg)
            return False

        # If both checks pass: Release Trigger
        logger.info(f"[Proof_Verification] INTEGRITY VERIFIED (100% Match). Triggering Escrow payout.")
        vendor_bank = account["vendor_assigned"]["bank"]
        release_success = self.oracle.release_funds(app_id, vendor_id, vendor_bank)
        
        if release_success:
            account["system_state"] = "Settled"
            logger.info(f"[Proof_Verification] Workflow completed. GCF/KOICA portal updated to: Settled.")
            return True
        
        return False


# --- Automated Pipeline Execution Test Suit ---
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  PROJECT ASTRAEA: MOCK ESCROW & VENDOR AUTOMATION PIPELINE")
    print("="*60 + "\n")

    # Initialize Oracle and Agents
    oracle = SmartContractOracle()
    admin_gateway = AdminGatewayAgent(oracle)
    vendor_dispatch = VendorDispatchAgent(oracle)
    proof_verification = ProofVerificationAgent(oracle)

    # ----------------------------------------------------
    # TEST CASE 1: Happy Path (Seoul, Korea Model Pilot)
    # ----------------------------------------------------
    print(">>> RUNNING TEST CASE 1: SUCCESSFUL END-TO-END WORKFLOW (KOREA) <<<")
    
    # GCF Webhook triggers approval
    approval_payload_1 = {
        "application_id": 1234,
        "status": "Approved",
        "allocated_grant_usd": 1500.0,
        "beneficiary_gps": (37.512, 127.118), # Songpa-gu coordinates
        "region": "South Korea"
    }
    
    # Phase 1: Initiation and Lock-up
    lock_success, tx_1 = admin_gateway.receive_approval_webhook(approval_payload_1)
    
    # Phase 2: Vendor Matching and Dispatch
    if lock_success:
        vendor_dispatch.match_and_dispatch(1234)

    # Phase 3 & 4: Upload proof & Auto-settlement
    proof_payload_1 = {
        "vendor_id": "KR_HP_02",
        "qr_data": "AST-QR-1234",
        "photo_quality": "HIGH" # Simulates valid upgrade paving detected by VLM
    }
    
    proof_verification.verify_delivery_proof(1234, proof_payload_1)
    print(f"Final State for App #1234: {json.dumps(oracle.get_account_status(1234), indent=2, ensure_ascii=False)}")
    print("\n" + "-"*60 + "\n")

    # ----------------------------------------------------
    # TEST CASE 2: Exception Handling - Delivery Timeout (US Pilot)
    # ----------------------------------------------------
    print(">>> RUNNING TEST CASE 2: EXCEPTION - 7-DAY DELIVERY TIMEOUT (USA) <<<")
    
    approval_payload_2 = {
        "application_id": 5678,
        "status": "Approved",
        "allocated_grant_usd": 3000.0,
        "beneficiary_gps": (32.825, -96.735), # Dallas coordinates
        "region": "USA"
    }
    
    lock_success_2, tx_2 = admin_gateway.receive_approval_webhook(approval_payload_2)
    if lock_success_2:
        vendor_dispatch.match_and_dispatch(5678)
        
    # Simulate 8 days of delay without upload
    vendor_dispatch.trigger_timeout_check(5678, days_elapsed=8)
    print("\n" + "-"*60 + "\n")

    # ----------------------------------------------------
    # TEST CASE 3: Exception Handling - Verification Mismatch (Kenya Pilot)
    # ----------------------------------------------------
    print(">>> RUNNING TEST CASE 3: EXCEPTION - VLM/QR VERIFICATION MISMATCH (KENYA) <<<")
    
    approval_payload_3 = {
        "application_id": 9012,
        "status": "Approved",
        "allocated_grant_usd": 1200.0,
        "beneficiary_gps": (-1.315, 36.790), # Kibera coordinates
        "region": "Kenya"
    }
    
    lock_success_3, tx_3 = admin_gateway.receive_approval_webhook(approval_payload_3)
    if lock_success_3:
        vendor_dispatch.match_and_dispatch(9012)
        
    # Vendor uploads fraud QR scan/low-quality photo (e.g. no concrete paving matched)
    proof_payload_3 = {
        "vendor_id": "KE_KT_01",
        "qr_data": "AST-QR-MALICIOUS-9999", # QR Mismatch!
        "photo_quality": "LOW"
    }
    
    proof_verification.verify_delivery_proof(9012, proof_payload_3)
    print(f"Final State for App #9012: {json.dumps(oracle.get_account_status(9012), indent=2, ensure_ascii=False)}")
    print("\n" + "="*60)
