import json
import time
import logging
import hashlib
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AstraeaMultiTenant")

# Simple encryption simulation for PII (Field-level Encryption)
def encrypt_pii(text, key="astraea-secret-2026"):
    # Base64-like simple cipher for demonstration
    cipher = []
    for i, char in enumerate(text):
        key_c = key[i % len(key)]
        cipher_c = chr(ord(char) ^ ord(key_c))
        cipher.append(cipher_c)
    return "".join(cipher).encode("utf-8").hex()

def decrypt_pii(hex_str, key="astraea-secret-2026"):
    try:
        text = bytes.fromhex(hex_str).decode("utf-8")
        decrypted = []
        for i, char in enumerate(text):
            key_c = key[i % len(key)]
            decrip_c = chr(ord(char) ^ ord(key_c))
            decrypted.append(decrip_c)
        return "".join(decrypted)
    except Exception:
        return "[DEC_FAIL]"


class SSOTenantGateway:
    """
    Agent 1 [SSO_Tenant_Gateway]
    Validates identity via email domains (KOICA, UN-Habitat, GCF) and issues secure tenant-scoped tokens.
    """
    def __init__(self):
        # Configured tenant domains and OIDC integration parameters
        self.tenant_registry = {
            "koica.go.kr": {"tenant_id": "KOICA_001", "name": "Korea International Cooperation Agency", "protocol": "OIDC"},
            "unhabitat.org": {"tenant_id": "UN_HABITAT_002", "name": "UN-Habitat", "protocol": "SAML 2.0"},
            "greenclimate.fund": {"tenant_id": "GCF_003", "name": "Green Climate Fund", "protocol": "OIDC"}
        }
        self.secret_signature = "AstraeaJwtSignatureKey_2026"

    def authenticate_sso(self, email, password_mock="password"):
        domain = email.split("@")[-1]
        tenant_info = self.tenant_registry.get(domain)

        if not tenant_info:
            logger.error(f"[SSO_Gateway] Unauthorized domain '{domain}'. SSO integration not found.")
            return None

        # Simulate OIDC/SAML handshake
        logger.info(f"[SSO_Gateway] Redirecting user to {tenant_info['protocol']} SSO for {tenant_info['name']}")
        logger.info(f"[SSO_Gateway] SSO login successful for {email}. Issuing JWT token.")

        # Construct JWT payload
        jwt_payload = {
            "email": email,
            "tenant_id": tenant_info["tenant_id"],
            "role": "Admin",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600
        }
        
        # Simple cryptographic signature (HMAC-SHA256 simulation)
        payload_str = json.dumps(jwt_payload, sort_keys=True)
        signature = hashlib.sha256((payload_str + self.secret_signature).encode("utf-8")).hexdigest()
        
        token = {
            "payload": jwt_payload,
            "signature": signature
        }
        return token

    def verify_token(self, token):
        if not token or "payload" not in token or "signature" not in token:
            logger.warning("[SSO_Gateway] Token verification failed: Malformed token payload.")
            return None

        payload_str = json.dumps(token["payload"], sort_keys=True)
        expected_sig = hashlib.sha256((payload_str + self.secret_signature).encode("utf-8")).hexdigest()

        if token["signature"] != expected_sig:
            logger.error("[SSO_Gateway] Token signature verification failed! Possible tampering.")
            return None

        # Expiry check
        if time.time() > token["payload"]["exp"]:
            logger.warning("[SSO_Gateway] Token has expired.")
            return None

        return token["payload"]


class RLSQueryGuardian:
    """
    Agent 2 [RLS_Query_Guardian]
    Enforces Row-Level Security. Scopes all DB inquiries and database inputs.
    Defends against cross-tenant injection vectors.
    """
    def __init__(self, database_connection, audit_logger):
        self.db = database_connection
        self.audit = audit_logger

    def execute_secured_select(self, table_name, token_payload):
        """
        Zero-Trust Database Interceptor: Scopes requests with tenant_id constraints.
        """
        if not token_payload or "tenant_id" not in token_payload:
            # Audit log security breach attempt
            self.audit.log_action("SYSTEM_GATEWAY", "UNAUTHORIZED", "SELECT_REJECTED", "Access denied: Missing tenant token")
            return {"error": "403 Forbidden: Missing Tenant Context"}, 403

        tenant_id = token_payload["tenant_id"]
        admin_email = token_payload["email"]
        logger.info(f"[RLS_Guardian] Intercepting read on table '{table_name}' for Admin '{admin_email}'. Query scoped to WHERE tenant_id = '{tenant_id}'")

        # Query execution with enforced Row-Level Security
        all_records = self.db.get_table_data(table_name)
        scoped_records = [rec for rec in all_records if rec.get("tenant_id") == tenant_id]

        # Log audit footprint
        self.audit.log_action(admin_email, tenant_id, "READ", f"Retrieved {len(scoped_records)} rows from '{table_name}'")
        return scoped_records, 200

    def execute_secured_insert(self, table_name, record_data, token_payload):
        """
        Forces alignment of tenant ID on insertion.
        """
        if not token_payload or "tenant_id" not in token_payload:
            self.audit.log_action("SYSTEM_GATEWAY", "UNAUTHORIZED", "INSERT_REJECTED", f"Write blocked on '{table_name}': Missing token")
            return {"error": "403 Forbidden: Write Scoping Failed"}, 403

        tenant_id = token_payload["tenant_id"]
        admin_email = token_payload["email"]
        
        # Enforce Row-Level Scoping constraint: Bind tenant_id
        record_data["tenant_id"] = tenant_id
        
        logger.info(f"[RLS_Guardian] Validating insert in table '{table_name}'. Forcing tenant_id mapping to '{tenant_id}'")
        self.db.insert_record(table_name, record_data)
        
        # Log audit trail
        self.audit.log_action(admin_email, tenant_id, "WRITE", f"Created new record in '{table_name}' with RLS binding")
        return {"status": "RECORD_CREATED_RLS_ENFORCED"}, 201


class DashboardUIBuilder:
    """
    Agent 3 [Dashboard_UI_Builder]
    Renders custom white-label dashboard widgets, configurations, and themes depending on tenant_id context.
    """
    def __init__(self):
        # White label profile configurations
        self.theme_configs = {
            "KOICA_001": {
                "logo": "https://brand.koica.go.kr/assets/koica_emblem_logo.png",
                "primary_color": "#0F4C81", # Indigo blue
                "accent_color": "#ffb703",
                "custom_domain": "koica.project-astraea.org",
                "custom_widget": "KOICA-GCF Climate Resilience Fund Widget"
            },
            "UN_HABITAT_002": {
                "logo": "https://unhabitat.org/themes/custom/unhabitat/logo.svg",
                "primary_color": "#009ADF", # UN Sky blue
                "accent_color": "#28a745",
                "custom_domain": "unhabitat.project-astraea.org",
                "custom_widget": "UN-Habitat Global Slum Upgrades Ledger Tracker"
            },
            "GCF_003": {
                "logo": "https://www.greenclimate.fund/themes/custom/gcf/logo.png",
                "primary_color": "#007A33", # Deep Green
                "accent_color": "#e0a800",
                "custom_domain": "gcf.project-astraea.org",
                "custom_widget": "Green Climate Fund Carbon Resilience Impact Widget"
            }
        }

    def compile_admin_dashboard(self, token_payload, data_payload):
        tenant_id = token_payload["tenant_id"]
        profile = self.theme_configs.get(tenant_id)

        if not profile:
            logger.error(f"[UI_Builder] Invalid tenant profile context for {tenant_id}")
            return {"error": "Tenant profile mapping not found"}

        logger.info(f"[UI_Builder] Resolving white-label parameters for Domain: {profile['custom_domain']}. Injecting Theme Color: {profile['primary_color']}")
        
        # Dynamic widget composition
        dashboard_manifest = {
            "white_label": {
                "organization_logo": profile["logo"],
                "color_palette": {
                    "primary": profile["primary_color"],
                    "accent": profile["accent_color"]
                },
                "domain_routing": profile["custom_domain"]
            },
            "enforced_widgets": [
                "Intake Audit Queue",
                "Whitelisted Material Vendors Map",
                profile["custom_widget"]
            ],
            "data_context": data_payload
        }
        return dashboard_manifest


class MockUnifiedDatabase:
    """
    Simulated Shared Database containing applications and vendors tables.
    Includes Field-level Encryption on beneficiary contact details.
    """
    def __init__(self):
        self.tables = {
            "applications": [
                {"id": 101, "tenant_id": "KOICA_001", "name": "Kim Min-soo", "contact": encrypt_pii("+82 10-1234-5678"), "hevi": 69.5, "escrow_status": "LOCKED"},
                {"id": 102, "tenant_id": "KOICA_001", "name": "Park Ji-young", "contact": encrypt_pii("+82 10-9876-5432"), "hevi": 72.4, "escrow_status": "LOCKED"},
                {"id": 201, "tenant_id": "UN_HABITAT_002", "name": "Juma Omwamba", "contact": encrypt_pii("+254 712 345678"), "hevi": 84.1, "escrow_status": "RELEASED"},
                {"id": 202, "tenant_id": "UN_HABITAT_002", "name": "Fatuma Ali", "contact": encrypt_pii("+254 789 123456"), "hevi": 79.8, "escrow_status": "LOCKED"}
            ],
            "vendors": [
                {"id": "V_KR_01", "tenant_id": "KOICA_001", "name": "LX Hausys Materials", "bank_account": "KB_Bank_394-01-2093"},
                {"id": "V_KE_01", "tenant_id": "UN_HABITAT_002", "name": "Kibera Timber Depot", "bank_account": "M-Pesa_Till_298492"}
            ]
        }

    def get_table_data(self, table_name):
        return self.tables.get(table_name, [])

    def insert_record(self, table_name, record_data):
        if table_name not in self.tables:
            self.tables[table_name] = []
        self.tables[table_name].append(record_data)


class AuditTrailLogger:
    """
    Database of immutable administrative transactions (Audit Log table).
    """
    def __init__(self):
        self.audit_log_db = []

    def log_action(self, admin_id, tenant_id, action, description):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "admin_id": admin_id,
            "tenant_id": tenant_id,
            "action": action,
            "description": description
        }
        self.audit_log_db.append(log_entry)
        logger.info(f"[AUDIT_LOG_BULLETIN] | {log_entry['timestamp']} | Tenant: {tenant_id} | User: {admin_id} | Action: {action} | Desc: {description}")

    def fetch_all_logs(self):
        return self.audit_log_db


# --- Multi-Tenant Portal Simulation Script ---
if __name__ == "__main__":
    print("\n" + "="*70)
    print("  PROJECT ASTRAEA: MULTI-TENANT B2G ADMIN PORTAL SIMULATOR")
    print("="*70 + "\n")

    # Initialize Core Architecture Components
    db = MockUnifiedDatabase()
    audit_logger = AuditTrailLogger()
    sso_gateway = SSOTenantGateway()
    rls_guardian = RLSQueryGuardian(db, audit_logger)
    ui_builder = DashboardUIBuilder()

    # ----------------------------------------------------
    # TEST CASE 1: KOICA Admin SSO Login & RLS Verification
    # ----------------------------------------------------
    print(">>> RUNNING SCENARIO 1: KOICA ADMIN LOGS IN AND FEEDS DASHBOARD <<<")
    # KOICA Login
    koica_token = sso_gateway.authenticate_sso("auditor@koica.go.kr")
    verified_koica_payload = sso_gateway.verify_token(koica_token)

    if verified_koica_payload:
        # Load KOICA Specific Applications Scoped via Row-Level Security
        koica_applicants, status_code = rls_guardian.execute_secured_select("applications", verified_koica_payload)
        
        # Display Decrypted Contact Numbers showing Field Level Encryption integrity
        print("\n=== KOICA Logical Scoped Applications (Decrypted Contact Details) ===")
        for app in koica_applicants:
            decrypted_num = decrypt_pii(app["contact"])
            print(f"ID: {app['id']} | Beneficiary: {app['name']} | Contact: {decrypted_num} | HEVI Index: {app['hevi']}")

        # Build Dynamic White-Label Dashboard
        koica_dashboard = ui_builder.compile_admin_dashboard(verified_koica_payload, koica_applicants)
        print("\n--- KOICA White Label Config Object ---")
        print(json.dumps(koica_dashboard["white_label"], indent=2))
        print("Enforced Widgets:", koica_dashboard["enforced_widgets"])
        print("-"*70 + "\n")

    # ----------------------------------------------------
    # TEST CASE 2: UN-Habitat Admin SSO Login & Vendor Addition Isolation
    # ----------------------------------------------------
    print(">>> RUNNING SCENARIO 2: UN-HABITAT REGISTERING NEW LOCAL VENDOR <<<")
    un_token = sso_gateway.authenticate_sso("director@unhabitat.org")
    verified_un_payload = sso_gateway.verify_token(un_token)

    if verified_un_payload:
        # UN-Habitat attempts to insert a new vendor
        new_vendor = {
            "id": "V_KE_02",
            "name": "Nairobi Concrete Suppliers",
            "bank_account": "Equity_Bank_39801"
        }
        
        # RLS Guardian Intercepts insert to inject Tenant ID mapping automatically
        rls_guardian.execute_secured_insert("vendors", new_vendor, verified_un_payload)

        # Confirm isolation: fetch UN-Habitat Vendors
        un_vendors, _ = rls_guardian.execute_secured_select("vendors", verified_un_payload)
        print("\n=== UN-Habitat Active Vendors Database (RLS Isolated) ===")
        print(json.dumps(un_vendors, indent=2))

        # Cross check: Ensure KOICA cannot read UN-Habitat Vendor
        koica_vendors, _ = rls_guardian.execute_secured_select("vendors", verified_koica_payload)
        print("\n=== KOICA Active Vendors Database (RLS Isolated) ===")
        print(json.dumps(koica_vendors, indent=2))
        print("-"*70 + "\n")

    # ----------------------------------------------------
    # TEST CASE 3: Zero-Trust Security Interception (Intrusion Attempt)
    # ----------------------------------------------------
    print(">>> RUNNING SCENARIO 3: SECURITY DETECTOR (ZERO-TRUST COMPLIANCE) <<<")
    # Simulate a forged token attempt to bypass RLS mapping
    forged_token = {
        "payload": {
            "email": "hacker@malicious-node.xyz",
            "tenant_id": "UN_HABITAT_002", # Attempting to read UN-Habitat files
            "role": "Admin",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600
        },
        "signature": "forged_signature_bypass_attempt"
    }

    print("Authenticating forged token token payload...")
    verified_forged_payload = sso_gateway.verify_token(forged_token)

    # Guardian intercepts check
    if not verified_forged_payload:
        print("[Security_Intercept] SSO validation intercepted forged signature. Interception logged.")
        # Triggering a raw request rejection simulation
        blocked_res, err_status = rls_guardian.execute_secured_select("applications", verified_forged_payload)
        print(f"RLS Query Guardian response code: {err_status} | Payload: {blocked_res}")
    
    print("\n" + "="*70)
