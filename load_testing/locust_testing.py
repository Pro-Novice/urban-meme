from locust import HttpUser, task, between, tag
import random
import string
import json
import os

# ---------- Helpers ----------
def random_string(length=6):
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return "".join(random.choice(chars) for _ in range(length))

def random_aadhaar():
    # 12-digit numeric string
    return str(random.randint(10**11, 10**12 - 1))

def random_txhash():
    hexchars = "0123456789abcdef"
    return "0x" + "".join(random.choice(hexchars) for _ in range(64))

def ok(resp):
    return 200 <= resp.status_code < 300

# Optional: override host via ENV if you prefer (else pass --host on CLI)
DEFAULT_HOST = os.getenv("LOCUST_HOST", "http://10.70.233.251:8000")

# ---------- Locust user ----------
class LicenseBlockchainUser(HttpUser):
    """
    Simulates a user performing your full license flow:
      1) owner init + check
      2) license count
      3) create license
      4) verify license
      5) update license
      6) get license info/history/qr
      7) update license status
      8) query random tx
      9) contract metadata
    """
    wait_time = between(1, 3)
    host = DEFAULT_HOST  # can be overridden with --host

    # You can add a bearer token if your API needs auth:
    # e.g., export LOCUST_TOKEN="Bearer eyJ..."
    def _headers(self):
        token = os.getenv("LOCUST_TOKEN")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = token
        return headers

    @task
    @tag("happy_path")
    def license_flow(self):
        # 1 & 2. Initialize/check owner
        with self.client.get("/api/blockchain/owner/", name="GET /owner (init)", catch_response=True) as r:
            r.success() if ok(r) else r.failure(f"Owner init failed: {r.status_code} {r.text[:200]}")
        with self.client.get("/api/blockchain/owner/", name="GET /owner (check)", catch_response=True) as r:
            r.success() if ok(r) else r.failure(f"Owner check failed: {r.status_code} {r.text[:200]}")

        # 3. License count
        with self.client.get("/api/blockchain/license/count/", name="GET /license/count", catch_response=True) as r:
            r.success() if ok(r) else r.failure(f"Count failed: {r.status_code} {r.text[:200]}")

        # 4. Create license
        license_payload = {
            "license_category": "AGRICULTURE",
            "license_level": "STATE",
            "registering_authority": "JOINT_DIRECTOR",
            "registering_office_name": "Office " + random_string(),
            "applicant_name": "User " + random_string(),
            "aadhaar_number": random_aadhaar(),
            "applicant_permanent_address": "Address " + random_string(),
            "firm_name": "Firm " + random_string(),
            "firm_type": "LLP",
            "firm_address": "Firm Addr " + random_string(),
            "sale_point_address": "Sale Addr",
            "sale_storage_address": "Storage Addr",
            "production_company": "Company X",
            "crop_name": "Wheat",
            "crop_variety": "Golden",
        }
        with self.client.post(
            "/api/blockchain/license/create/",
            data=json.dumps(license_payload),
            headers=self._headers(),
            name="POST /license/create",
            catch_response=True,
        ) as r:
            created_id = None
            if ok(r):
                try:
                    body = r.json()
                    # Try common keys—adapt to your API's response
                    created_id = body.get("license_id") or body.get("id") or 1
                    r.success()
                except Exception:
                    # If response isn't JSON, still mark success but note it
                    r.success()
            else:
                r.failure(f"Create failed: {r.status_code} {r.text[:200]}")

        # 5. Verify license (dummy expected hash)
        verify_payload = {"license_number": "1", "expected_hash": "dummyhashvalue123456789"}
        with self.client.post(
            "/api/blockchain/license/verify/",
            data=json.dumps(verify_payload),
            headers=self._headers(),
            name="POST /license/verify",
            catch_response=True,
        ) as r:
            r.success() if ok(r) else r.failure(f"Verify failed: {r.status_code} {r.text[:200]}")

        # 6. Update license (use created_id if available; fallback to 1)
        target_id = created_id or 1
        update_payload = {
            "license_id": target_id,
            "firm_name": "Updated Firm",
            "firm_type": "PVT",
            "firm_address": "Updated Addr",
            "sale_point_address": "Updated Sale",
            "sale_storage_address": "Updated Storage",
            "production_company": "Updated Co",
            "crop_name": "Corn",
            "crop_variety": "Sweet",
            "role": "JOINT_DIRECTOR",
        }
        with self.client.post(
            "/api/blockchain/license/update/",
            data=json.dumps(update_payload),
            headers=self._headers(),
            name="POST /license/update",
            catch_response=True,
        ) as r:
            r.success() if ok(r) else r.failure(f"Update failed: {r.status_code} {r.text[:200]}")

        # 7. Info/history/QR for a random id 1..5 (or created)
        license_id = target_id if isinstance(target_id, int) else random.randint(1, 5)
        for endpoint, short in [
            (f"/api/blockchain/license/{license_id}/info/", "info"),
            (f"/api/blockchain/license/{license_id}/history/", "history"),
            (f"/api/blockchain/license/{license_id}/qr/", "qr"),
        ]:
            with self.client.get(endpoint, name=f"GET /license/:id/{short}", catch_response=True) as r:
                r.success() if ok(r) else r.failure(f"{short} failed: {r.status_code} {r.text[:200]}")

        # 8. Update license status
        status_payload = {
            "license_id": target_id,
            "status": "APPROVED",
            "remarks": "All documents verified.",
            "officer_name": "Officer X",
            "role": "JOINT_DIRECTOR",
            "renewal_period_days": 365,
        }
        with self.client.post(
            "/api/blockchain/license/update-status/",
            data=json.dumps(status_payload),
            headers=self._headers(),
            name="POST /license/update-status",
            catch_response=True,
        ) as r:
            r.success() if ok(r) else r.failure(f"Status update failed: {r.status_code} {r.text[:200]}")

        # 9. Transaction status (random hash)
        with self.client.get(
            f"/api/blockchain/transaction/{random_txhash()}/",
            name="GET /transaction/:hash",
            catch_response=True,
        ) as r:
            # Often 404 is expected if tx doesn't exist—treat 200-404 as OK if that's your contract
            if r.status_code in (200, 202, 404):
                r.success()
            else:
                r.failure(f"Tx query failed: {r.status_code} {r.text[:200]}")

        # 10. Contract info
        base = "/api/blockchain/contract/LicenseSystemV1"
        for path in ["/address/", "/methods/", "/abi/"]:
            with self.client.get(base + path, name=f"GET /contract{path}", catch_response=True) as r:
                r.success() if ok(r) else r.failure(f"Contract {path} failed: {r.status_code} {r.text[:200]}")
