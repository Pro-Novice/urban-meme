# locustfile.py
from locust import HttpUser, task, between, events
import os, time, uuid, json, random, string
from threading import Lock
import re  # NEW

# ========= Config via env =========
BASE_URL   = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")           # e.g. JWT token
DO_HEAVY_MUTATIONS = os.getenv("DO_HEAVY_MUTATIONS", "1") == "1"  # toggle POST/PUT steps
USE_VERHOEFF_AADHAAR = os.getenv("USE_VERHOEFF_AADHAAR", "1") == "1"

# ========= One-time init (per worker process) =========
_init_lock = Lock()
_initialized = False
_init_ok = True  # flipped to False if init fails so users can bail fast

@events.test_start.add_listener
def _warm_once(environment, **kw):
    """
    Run once per worker process at test start.
    Uses the runner's environment to spin a lightweight client and warm endpoints.
    """
    global _initialized, _init_ok
    with _init_lock:
        if _initialized:
            return
        # If there is no runner (e.g., web UI not started), skip
        if not environment or not environment.parsed_options:
            _initialized = True
            return

        from locust.util.exception_handler import catch_exceptions
        from requests import Session

        s = Session()
        s.headers.update({"Content-Type": "application/json"})
        if AUTH_TOKEN:
            s.headers["Authorization"] = f"Bearer {AUTH_TOKEN}"

        url = BASE_URL + "/api/blockchain/owner/"
        try:
            with catch_exceptions():
                r = s.get(url, timeout=15)
                if r.status_code >= 400:
                    raise RuntimeError(f"Warmup failed {r.status_code}: {r.text[:200]}")
        except Exception as e:
            _init_ok = False
            print(f"[INIT] Failed warming {url}: {e}")
        finally:
            _initialized = True

# ========= Helpers =========
def uniq(prefix: str) -> str:
    # ms epoch + short uuid: unique under load
    return f"{prefix}-{int(time.time()*1000)}-{uuid.uuid4().hex[:8]}"

def random_string(n=6) -> str:
    return "".join(random.choices(string.ascii_letters, k=n))

# ---- Verhoeff checksum (correct 12-digit Aadhaar) ----
_d_table = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,2,3,4,0,6,7,8,9,5],
    [2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],
    [4,0,1,2,3,9,5,6,7,8],
    [5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],
    [7,6,5,9,8,2,1,0,4,3],
    [8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]
_p_table = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,5,7,6,2,8,3,0,9,4],
    [5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],
    [9,4,5,3,1,2,6,8,7,0],
    [4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],
    [7,0,4,6,9,1,3,2,5,8],
]
_inv_table = [0,4,3,2,1,5,6,7,8,9]

def verhoeff_check_digit(num_str: str) -> str:
    c = 0
    # Correct iteration: use i % 8 (not (i+1) % 8)
    for i, ch in enumerate(reversed(num_str)):
        c = _d_table[c][_p_table[i % 8][int(ch)]]
    return str(_inv_table[c])

def random_aadhaar() -> str:
    if not USE_VERHOEFF_AADHAAR:
        return str(random.randint(10**11, 10**12 - 1))  # 12 digits, no checksum
    base11 = str(random.randint(10**10, 10**11 - 1))    # 11 digits
    return base11 + verhoeff_check_digit(base11)        # 12 digits total

def random_txhash():
    return "0x" + "".join(random.choice("0123456789abcdef") for _ in range(64))

def today_date():
    return time.strftime("%Y-%m-%d")

# ---- Robust response parsing helpers (NEW) ----
def _content_type(resp):
    try:
        return (resp.headers.get("Content-Type") or "").lower()
    except Exception:
        return ""

def _extract_license_id(resp):
    """
    Try to get license_id from:
    1) JSON
    2) Location header (/license/<id>/...)
    3) Plain text or HTML containing `"license_id": 123` or `"id": 123`
    Returns str/int or None.
    """
    if not resp:
        return None

    ct = _content_type(resp)
    body = resp.text or ""

    # 1) JSON body
    if "application/json" in ct or body.startswith("{") or body.startswith("["):
        try:
            data = resp.json() or {}
            return (
                data.get("license_id")
                or data.get("id")
                or (data.get("data") or {}).get("license_id")
            )
        except Exception:
            pass

    # 2) Location header (e.g., 201 Created)
    loc = resp.headers.get("Location") or resp.headers.get("location")
    if loc:
        m = re.search(r"/license/(\d+)", loc)
        if m:
            return m.group(1)

    # 3) Text/HTML regex
    for key in ("license_id", "id"):
        m = re.search(rf'"{key}"\s*:\s*"?(\d+)"?', body)
        if m:
            return m.group(1)

    return None

# ========= Log failing responses for quick triage =========
@events.request.add_listener
def log_bad_requests(request_type, name, response_time, response_length, response, context, exception, **kw):
    if exception:
        print(f"[{request_type} {name}] EXC: {exception}")
    elif response is not None and response.status_code >= 400:
        body = (response.text or "")[:800]
        print(f"[{request_type} {name}] {response.status_code} BODY: {body}")

# ========= User Scenario =========
class LicenseBlockchainUser(HttpUser):
    wait_time = between(1, 3)
    host = BASE_URL  # supports http(s)://host:port, no trailing slash needed

    def _headers(self, extra=None):
        h = {"Content-Type": "application/json"}
        if AUTH_TOKEN:
            h["Authorization"] = f"Bearer {AUTH_TOKEN}"
        if extra:
            h.update(extra)
        return h

    def on_start(self):
        # If warmup failed, fail this user quickly so you see the root cause in the logs
        if not _init_ok:
            raise RuntimeError("Global init/warmup failed; fix the /owner endpoint before load testing.")

        # Optional: small retry adapter for transient 502/503/504, timeouts, etc. (NEW)
        try:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            retry = Retry(
                total=2,
                backoff_factor=0.2,
                status_forcelist=[502, 503, 504],
                allowed_methods=frozenset(["GET","POST","PUT","DELETE","PATCH","HEAD","OPTIONS"]),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            self.client.session.mount("http://", adapter)
            self.client.session.mount("https://", adapter)
        except Exception as e:
            # Non-fatal if urllib3/requests versions differ
            print(f"[on_start] Retry adapter not set: {e}")

    @task
    def workflow(self):
        # 1) Quick reads
        self.client.get("/api/blockchain/owner/", headers=self._headers(), name="GET /owner")
        self.client.get("/api/blockchain/license/count/", headers=self._headers(), name="GET /license/count")

        if DO_HEAVY_MUTATIONS:
            # 2) Create license (robust, transport-safe)
            license_payload = {
                "license_category": "SEED",
                "license_level": "STATE",
                "registering_authority": "JOINT_DIRECTOR",
                "registering_office_name": f"Office {random_string()}",
                "applicant_name": f"User {random_string()}",
                "aadhaar_number": random_aadhaar(),
                "applicant_permanent_address": f"Address {random_string()}",
                "firm_name": f"{uniq('Firm')}",
                "firm_type": "LLP",
                "firm_address": f"Firm Addr {random_string()}",
                "sale_point_address": f"Sale {random_string()}",
                "sale_storage_address": f"Storage {random_string()}",
                "production_company": f"Company {random_string()}",
                "crop_name": "Wheat",
                "crop_variety": "Golden",
                # "issue_date": today_date(),
            }
            headers = self._headers({"Idempotency-Key": uuid.uuid4().hex})

            license_id = None
            try:
                with self.client.post(
                    "/api/blockchain/license/create/",
                    json=license_payload,
                    headers=headers,
                    name="POST /license/create",
                    timeout=30,                 # ↑ a bit higher
                    catch_response=True,
                    allow_redirects=False,      # so we can use Location header if present
                ) as r:
                    if r is None:
                        r.failure("No response object (transport error)")
                        return

                    code = r.status_code or 0
                    if code >= 500:
                        r.failure(f"Server error {code}: {r.text[:200]}")
                        return
                    if code >= 400:
                        r.failure(f"Client error {code}: {r.text[:200]}")
                        return

                    license_id = _extract_license_id(r)
                    if not license_id:
                        ct = _content_type(r)
                        snippet = (r.text or "")[:200]
                        r.failure(f"Could not extract license_id | CT={ct} | Body[:200]={snippet!r}")
                        return

                    r.success()
            except Exception as e:
                # Connection dropped, DNS, timeout, etc.
                self.environment.events.request.fire(
                    request_type="POST",
                    name="POST /license/create",
                    response_time=30000,
                    response_length=0,
                    exception=e,
                    context={},
                    response=None,
                )
                return

            # If we couldn't obtain the ID, skip dependent calls
            if not license_id:
                return

            # 3) Verify license document (robust, longer timeout)
            verify_payload = {"license_number": str(license_id), "expected_hash": "dummyhashvalue123456789"}
            try:
                with self.client.post(
                    "/api/blockchain/license/verify/",
                    json=verify_payload,
                    headers=self._headers(),
                    name="POST /license/verify",
                    timeout=60,              # ↑ bump from 20 -> 60
                    catch_response=True,
                ) as r:
                    code = (r.status_code or 0) if r else 0
                    if not r or code >= 500:
                        (r and r.failure(f"Server error {code}: {r.text[:200]}")) or None
                        return
                    if code >= 400:
                        r.failure(f"Client error {code}: {r.text[:200]}")
                        return
                    r.success()
            except Exception as e:
                self.environment.events.request.fire(
                    request_type="POST",
                    name="POST /license/verify",
                    response_time=30000,
                    response_length=0,
                    exception=e,
                    context={},
                    response=None,
                )
                return

            # 4) Update license details (robust)
            update_payload = {
                "license_id": license_id,
                "firm_name": f"Updated {random_string()}",
                "firm_type": "PVT",
                "firm_address": f"Updated Addr {random_string()}",
                "sale_point_address": f"Updated Sale {random_string()}",
                "sale_storage_address": f"Updated Storage {random_string()}",
                "production_company": f"Updated Co {random_string()}",
                "crop_name": "Corn",
                "crop_variety": "Sweet",
                "role": "JOINT_DIRECTOR",
            }
            try:
                with self.client.post(
                    "/api/blockchain/license/update/",
                    json=update_payload,
                    headers=self._headers(),
                    name="POST /license/update",
                    timeout=30,
                    catch_response=True,
                ) as r:
                    code = (r.status_code or 0) if r else 0
                    if not r or code >= 500:
                        (r and r.failure(f"Server error {code}: {r.text[:200]}")) or None
                        return
                    if code >= 400:
                        r.failure(f"Client error {code}: {r.text[:200]}")
                        return
                    r.success()
            except Exception as e:
                self.environment.events.request.fire(
                    request_type="POST",
                    name="POST /license/update",
                    response_time=30000,
                    response_length=0,
                    exception=e,
                    context={},
                    response=None,
                )
                return

            # 5) Reads by id (simple GETs)
            self.client.get(f"/api/blockchain/license/{license_id}/info/",    headers=self._headers(), name="GET /license/:id/info")
            self.client.get(f"/api/blockchain/license/{license_id}/history/", headers=self._headers(), name="GET /license/:id/history")
            self.client.get(f"/api/blockchain/license/{license_id}/qr/",      headers=self._headers(), name="GET /license/:id/qr")

            # 6) Status update (robust)
            status_payload = {
                "license_id": license_id,
                "status": "APPROVED",
                "remarks": "All documents verified.",
                "officer_name": "Officer X",
                "role": "JOINT_DIRECTOR",
                "renewal_period_days": 365,
            }
            try:
                with self.client.post(
                    "/api/blockchain/license/update-status/",
                    json=status_payload,
                    headers=self._headers(),
                    name="POST /license/update-status",
                    timeout=30,
                    catch_response=True,
                ) as r:
                    code = (r.status_code or 0) if r else 0
                    if not r or code >= 500:
                        (r and r.failure(f"Server error {code}: {r.text[:200]}")) or None
                        return
                    if code >= 400:
                        r.failure(f"Client error {code}: {r.text[:200]}")
                        return
                    r.success()
            except Exception as e:
                self.environment.events.request.fire(
                    request_type="POST",
                    name="POST /license/update-status",
                    response_time=30000,
                    response_length=0,
                    exception=e,
                    context={},
                    response=None,
                )
                return

        # 7) Transaction status (random hash)
        self.client.get(f"/api/blockchain/transaction/{random_txhash()}/", headers=self._headers(), name="GET /transaction/:hash")

        # 8) Contract info
        base = "/api/blockchain/contract/LicenseSystemV1"
        self.client.get(f"{base}/address/", headers=self._headers(), name="GET /contract/address")
        self.client.get(f"{base}/methods/", headers=self._headers(), name="GET /contract/methods")
        self.client.get(f"{base}/abi/",     headers=self._headers(), name="GET /contract/abi")
