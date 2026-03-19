import pytest
from unittest.mock import MagicMock, patch
from utils.encrypt_aadhaar import encrypt_aadhaar
from apps.seed_licenses.services.license_service import LicenseService, TransactionService
from apps.seed_licenses.services.multi_account_manager import multi_account_manager
from django.core.cache import cache as django_cache


# =============================================================================
# Blockchain State Manager
# =============================================================================

class BlockchainStateManager:
    """
    In-memory blockchain state simulator — one independent instance per test.
    """

    STATUS_MAP = {
        0: "SUBMITTED",            1: "UNDER_REVIEW",
        2: "DOCUMENTS_VERIFIED",   3: "INSPECTION_SCHEDULED",
        4: "INSPECTION_COMPLETED", 5: "APPROVED",
        6: "REJECTED",             7: "REVOKED",
        8: "EXPIRED",              9: "RENEWED",
    }
    STATUS_REVERSE = {v: k for k, v in STATUS_MAP.items()}

    CATEGORY_MAP     = {0: "SEED", 1: "FERTILIZER", 2: "PESTICIDE"}
    CATEGORY_REVERSE = {v: k for k, v in CATEGORY_MAP.items()}

    LEVEL_MAP     = {0: "STATE", 1: "DIVISION", 2: "DISTRICT"}
    LEVEL_REVERSE = {v: k for k, v in LEVEL_MAP.items()}

    ROLE_MAP = {
        0: "CITIZEN",                       1: "AGRICULTURE_OFFICER",
        2: "ASSISTANT_AGRICULTURE_OFFICER", 3: "ASSISTANT_DIRECTOR",
        4: "DEPUTY_DIRECTOR",               5: "JOINT_DIRECTOR",
        6: "JOINT_DIRECTOR_INPUT",          7: "FIELD_INSPECTOR",
    }
    ROLE_REVERSE = {v: k for k, v in ROLE_MAP.items()}

    GEO_REQUIRED_CATEGORIES = {1, 2}   # FERTILIZER, PESTICIDE
    GEO_SCALE               = 1_000_000

    # FIX-1: all state is instance-level — no class-level dict
    def __init__(self):
        self._accounts = [
            {
                "address":     "0x0000000000000000000000000000000000000001",
                "private_key": "TEST_PRIVATE_KEY",
                "source":      "test",
                "index":        0,
            }
        ]
        self._owner = "0x0000000000000000000000000000000000000001"
        self.reset()

    def reset(self):
        self._licenses        = {}   # int license_id -> dict
        self._license_numbers = {}   # str license_number -> int license_id
        self._counter         = 0

    # ── properties ────────────────────────────────────────────────────────

    @property
    def licenses(self):
        return self._licenses

    @property
    def license_numbers(self):
        return self._license_numbers

    @property
    def counter(self):
        return self._counter

    @counter.setter
    def counter(self, value):
        self._counter = value

    @property
    def owner(self):
        return self._owner

    @property
    def accounts(self):
        return self._accounts

    # ── helpers ──────────────────────────────────────────────────────────

    def _resolve_license_id(self, license_id_or_number):
        if isinstance(license_id_or_number, int):
            return license_id_or_number
        lid = self._license_numbers.get(license_id_or_number)
        if lid is None:
            raise Exception(f"License number '{license_id_or_number}' does not exist")
        return lid

    def transform_license_data(self, raw):
        if isinstance(raw, (list, tuple)):
            data = {
                "licenseId":               raw[0]  if len(raw) > 0  else None,
                "licenseNumber":           raw[1]  if len(raw) > 1  else None,
                "applicantName":           raw[2]  if len(raw) > 2  else None,
                "category":                raw[3]  if len(raw) > 3  else None,
                "level":                   raw[4]  if len(raw) > 4  else None,
                "status":                  raw[5]  if len(raw) > 5  else None,
                "firmName":                raw[6]  if len(raw) > 6  else None,
                "firmType":                raw[7]  if len(raw) > 7  else None,
                "firmAddress":             raw[8]  if len(raw) > 8  else None,
                "salePointAddress":        raw[9]  if len(raw) > 9  else None,
                "saleStorageAddress":      raw[10] if len(raw) > 10 else None,
                "productionCompany":       raw[11] if len(raw) > 11 else None,
                "cropName":                raw[12] if len(raw) > 12 else None,
                "cropVariety":             raw[13] if len(raw) > 13 else None,
                "registeringOfficeName":   raw[14] if len(raw) > 14 else None,
                "registeringAuthority":    raw[15] if len(raw) > 15 else None,
                "applicationDate":         raw[16] if len(raw) > 16 else None,
                "isActive":                raw[22] if len(raw) > 22 else None,
            }
        else:
            data = dict(raw)

        if isinstance(data.get("status"),   int):
            data["status"]   = self.STATUS_MAP.get(data["status"],   "UNKNOWN")
        if isinstance(data.get("category"), int):
            data["category"] = self.CATEGORY_MAP.get(data["category"], "UNKNOWN")
        if isinstance(data.get("level"),    int):
            data["level"]    = self.LEVEL_MAP.get(data["level"],    "UNKNOWN")

        return data

    # ── READ mock ─────────────────────────────────────────────────────────

    def mock_transaction_service_read(self, method_name, params):
        if method_name == "owner":
            return self._owner

        if method_name == "licenseIdCounter":
            return self._counter

        if method_name == "getLicenseBasicInfo":
            lid  = self._resolve_license_id(params[0])
            raw  = self._licenses.get(lid)
            if raw is None:
                raise Exception(f"License {lid} does not exist")
            data = self.transform_license_data(raw)

            # FIX-4: return float degrees (divide stored scaled int)
            category_int = raw.get("category", 0)
            if category_int in self.GEO_REQUIRED_CATEGORIES:
                raw_lat = raw.get("latitude",  0) or 0
                raw_lng = raw.get("longitude", 0) or 0
                data["latitude"]  = raw_lat / self.GEO_SCALE
                data["longitude"] = raw_lng / self.GEO_SCALE
            else:
                data.pop("latitude",  None)
                data.pop("longitude", None)

            data.pop("licenseId", None)
            return data

        if method_name == "getLicenseActionHistory":
            lid = self._resolve_license_id(params[0])
            raw = self._licenses.get(lid)
            if raw is None:
                raise Exception(f"License {lid} does not exist")
            result = []
            for item in raw.get("history", []):
                t = dict(item)
                if isinstance(t.get("actionType"), int):
                    t["actionType"] = self.STATUS_MAP.get(t["actionType"], "UNKNOWN")
                if isinstance(t.get("actorRole"),  int):
                    t["actorRole"]  = self.ROLE_MAP.get(t["actorRole"],  "UNKNOWN")
                result.append(t)
            return result

        if method_name == "getLicenseQRData":
            lid = self._resolve_license_id(params[0])
            raw = self._licenses.get(lid)
            if raw is None:
                raise Exception(f"License {lid} does not exist")
            if not raw.get("isActive", False):
                raise Exception("License must be active to generate QR data")
            return {
                "verificationHash": raw.get("verificationHash", ""),
                "licenseNumber":    raw.get("licenseNumber",    ""),
            }

        raise ValueError(f"Read method '{method_name}' not mocked")

    # ── WRITE mock ────────────────────────────────────────────────────────

    def mock_transaction_service_write(self, method_name, params,
                                       address=None, private_key=None):
        address = address or self._accounts[0]["address"]

        # ── submitLicenseApplicationV2 ────────────────────────────────────
        if method_name == "submitLicenseApplicationV2":
            struct = params[0]

            license_number = struct.get("licenseNumber") or ""

            # Duplicate check — view DB unique constraint handles this first,
            # but guard here too for robustness.
            if license_number and license_number in self._license_numbers:
                return {
                    "success": False,
                    "error":   f"License number '{license_number}' already exists",
                }

            self._counter += 1
            lid = self._counter

            if not license_number:
                license_number = f"RJSDST{lid}"

            category_int = struct.get("category", 0)

            # FIX-4: serializer already scaled lat/lng x1_000_000
            lat_scaled = struct.get("latitude",  0) or 0
            lng_scaled = struct.get("longitude", 0) or 0

            # FIX-3: geo validation returns {"success": False} so _tx_response
            # converts it to HTTP 400 cleanly (no 500).
            if category_int in self.GEO_REQUIRED_CATEGORIES:
                if not lat_scaled or not lng_scaled:
                    self._counter -= 1
                    return {
                        "success": False,
                        "error":   "latitude and longitude are required for FERTILIZER/PESTICIDE",
                    }
                lat_deg = lat_scaled / self.GEO_SCALE
                lng_deg = lng_scaled / self.GEO_SCALE
                if not (-90 <= lat_deg <= 90):
                    self._counter -= 1
                    return {
                        "success": False,
                        "error":   f"latitude {lat_deg} is out of valid range [-90, 90]",
                    }
                if not (-180 <= lng_deg <= 180):
                    self._counter -= 1
                    return {
                        "success": False,
                        "error":   f"longitude {lng_deg} is out of valid range [-180, 180]",
                    }
            else:
                # SEED: serializer strips lat/lng before we get here,
                # so this guard should never trigger in valid flows.
                if lat_scaled or lng_scaled:
                    self._counter -= 1
                    return {
                        "success": False,
                        "error":   "latitude and longitude are not allowed for SEED",
                    }

            self._licenses[lid] = {
                "licenseId":                 lid,
                "licenseNumber":             license_number,
                "applicantName":             struct["applicantName"],
                "category":                  category_int,
                "level":                     struct.get("level", 0),
                "status":                    0,
                "firmName":                  struct["firmName"],
                "firmType":                  struct["firmType"],
                "firmAddress":               struct["firmAddress"],
                "salePointAddress":          struct["salePointAddress"],
                "saleStorageAddress":        struct["saleStorageAddress"],
                "productionCompany":         struct.get("productionCompany", ""),
                "cropName":                  struct["cropName"],
                "cropVariety":               struct["cropVariety"],
                "registeringOfficeName":     struct["registeringOfficeName"],
                "registeringAuthority":      struct["registeringAuthority"],
                "applicantPermanentAddress": struct["applicantPermanentAddress"],
                "aadhaarNumber":             struct["aadhaarNumber"],
                "applicationDate":           1733270400,
                "isActive":                  True,
                "latitude":                  lat_scaled,   # FIX-4: scaled int
                "longitude":                 lng_scaled,   # FIX-4: scaled int
                "verificationHash":          f"hash_{lid}",
                "history": [{
                    "timestamp":  1733270400,
                    "actionType": 0,
                    "actorName":  struct["applicantName"],
                    "actorRole":  0,
                    "remarks":    "License Application Successfully Submitted",
                    "dataHash":   f"hash_{lid}",
                }],
            }
            self._license_numbers[license_number] = lid

            tx_hash = f"0xtx{lid}"

            # FIX-2: update the LicenseSubmission row the view already created
            # (without license_id) so info-by-number resolves immediately.
            try:
                from apps.seed_licenses.models import LicenseSubmission
                LicenseSubmission.objects.filter(
                    license_number=license_number
                ).update(
                    license_id=lid,
                    transaction_hash=tx_hash,
                )
            except Exception:
                pass

            return {
                "success":          True,
                "transaction_hash": tx_hash,
                "status":           "pending",
                "rpc_url":          "http://test:8545",
                "message":          "Transaction submitted successfully",
                "sender_address":   address,
                "license_number":   license_number,
            }

        # ── updateLicenseStatus ───────────────────────────────────────────
        if method_name == "updateLicenseStatus":
            lid, new_status, officer_name, role, remarks, renewal_period = params

            raw = self._licenses.get(lid)
            if raw is None:
                return {"success": False, "error": f"License {lid} does not exist"}

            raw["status"] = new_status

            if new_status in (5, 9):
                raw["isActive"] = True
            elif new_status in (6, 7):
                raw["isActive"] = False

            raw["history"].append({
                "timestamp":  1733270400,
                "actionType": new_status,
                "actorName":  officer_name,
                "actorRole":  role,
                "remarks":    remarks,
                "dataHash":   f"hash_status_{lid}_{new_status}",
            })

            return {
                "success":          True,
                "transaction_hash": f"0xtx_status_{lid}_{new_status}",
                "status":           "pending",
                "rpc_url":          "http://test:8545",
                "message":          "Transaction submitted successfully",
                "sender_address":   address,
            }

        # ── updateLicenseDetails ──────────────────────────────────────────
        if method_name == "updateLicenseDetails":
            lid = params[0]

            raw = self._licenses.get(lid)
            if raw is None:
                return {"success": False, "error": f"License {lid} does not exist"}

            if raw["status"] != 5:
                return {"success": False, "error": "License must be APPROVED to update details"}

            update_fields = [
                "firmName", "firmType", "firmAddress", "salePointAddress",
                "saleStorageAddress", "productionCompany", "cropName", "cropVariety",
            ]
            for i, field in enumerate(update_fields, 1):
                if i < len(params) and params[i]:
                    raw[field] = params[i]

            return {
                "success":          True,
                "transaction_hash": f"0xtx_update_{lid}",
                "status":           "pending",
                "rpc_url":          "http://test:8545",
                "message":          "Transaction submitted successfully",
                "sender_address":   address,
            }

        # ── verifyLicenseWithHash ─────────────────────────────────────────
        if method_name == "verifyLicenseWithHash":
            license_number, expected_hash = params

            lid = self._license_numbers.get(license_number)
            if lid is None:
                return {"success": False, "error": "License not found"}

            raw      = self._licenses[lid]
            verified = raw.get("verificationHash") == expected_hash

            return {
                "success":          True,
                "transaction_hash": f"0xtx_verify_{license_number}",
                "status":           "pending",
                "rpc_url":          "http://test:8545",
                "message":          "Transaction submitted successfully",
                "verified":         verified,
                "sender_address":   address,
            }

        raise ValueError(f"Write method '{method_name}' not mocked")


# =============================================================================
# Core fixtures
# =============================================================================

@pytest.fixture(scope="function")
def blockchain_state():
    """Fresh BlockchainStateManager per test function — no shared class state."""
    django_cache.clear()
    manager = BlockchainStateManager()
    yield manager
    manager.reset()
    django_cache.clear()


# =============================================================================
# Category-specific payload fixtures
# =============================================================================

@pytest.fixture
def seed_license_payload():
    """SEED license — latitude / longitude MUST NOT be present."""
    return {
        "licenseCategory":           "SEED",
        "licenseLevel":              "STATE",
        "registeringAuthority":      "Department of Agriculture",
        "registeringOfficeName":     "State Agriculture Office",
        "licenseNumber":             "RJSDST-TEST-001",
        "applicantName":             "Rajesh Kumar",
        "aadhaarNumber":             encrypt_aadhaar("234567890123"),
        "applicantPermanentAddress": "123 Main St, Jaipur, Rajasthan",
        "firmName":                  "Kumar Seeds Pvt Ltd",
        "firmType":                  "Private Limited",
        "firmAddress":               "456 Industrial Area, Jaipur",
        "salePointAddress":          "789 Market Road, Jaipur",
        "saleStorageAddress":        "101 Warehouse District, Jaipur",
        "cropName":                  "Wheat",
        "cropVariety":               "HD-2967",
        "productionCompany":         "Kumar Seeds Pvt Ltd",
        # NO latitude / longitude — SEED forbids them
    }


@pytest.fixture
def fertilizer_license_payload():
    """FERTILIZER license — latitude / longitude REQUIRED."""
    return {
        "licenseCategory":           "FERTILIZER",
        "licenseLevel":              "STATE",
        "registeringAuthority":      "Department of Agriculture",
        "registeringOfficeName":     "District Agri Office, Jaipur",
        "licenseNumber":             "RJFTST-TEST-001",
        "applicantName":             "Suresh Sharma",
        "aadhaarNumber":             encrypt_aadhaar("345678901234"),
        "applicantPermanentAddress": "456 MG Road, Jaipur, Rajasthan",
        "firmName":                  "Sharma Fertilizers Pvt Ltd",
        "firmType":                  "Private Limited",
        "firmAddress":               "Plot 45, Industrial Area, Jaipur",
        "salePointAddress":          "Shop 12, Market Road, Jaipur",
        "saleStorageAddress":        "Warehouse 3, NH-8, Jaipur",
        "cropName":                  "Wheat",
        "cropVariety":               "HD-2967",
        "productionCompany":         "AgriChem India Ltd",
        "latitude":                  26.9500,
        "longitude":                 75.6800,
    }


@pytest.fixture
def pesticide_license_payload():
    """PESTICIDE license — latitude / longitude REQUIRED."""
    return {
        "licenseCategory":           "PESTICIDE",
        "licenseLevel":              "DISTRICT",
        "registeringAuthority":      "Department of Agriculture",
        "registeringOfficeName":     "District Agri Office, Jodhpur",
        "licenseNumber":             "RJPSDT-TEST-001",
        "applicantName":             "Mohan Verma",
        "aadhaarNumber":             encrypt_aadhaar("456789012345"),
        "applicantPermanentAddress": "789 Station Road, Jodhpur, Rajasthan",
        "firmName":                  "Verma Pesticides Ltd",
        "firmType":                  "Public Limited",
        "firmAddress":               "Plot 22, RIICO Area, Jodhpur",
        "salePointAddress":          "Shop 5, Agri Market, Jodhpur",
        "saleStorageAddress":        "Godown 1, NH-65, Jodhpur",
        "cropName":                  "Cotton",
        "cropVariety":               "Bt Cotton",
        "productionCompany":         "ChemAgro India",
        "latitude":                  26.2900,
        "longitude":                 73.0200,
    }


@pytest.fixture
def complete_license_payload(seed_license_payload):
    """Backward-compatible alias."""
    return seed_license_payload


# =============================================================================
# Service / infrastructure fixtures
# =============================================================================

@pytest.fixture
def mock_transaction_service(blockchain_state):
    mock_svc = MagicMock(spec=TransactionService)
    mock_svc.read.side_effect  = blockchain_state.mock_transaction_service_read
    mock_svc.write.side_effect = blockchain_state.mock_transaction_service_write
    mock_svc.get_status.return_value = {
        "tx_hash":       "0xtest123",
        "status":        "CONFIRMED",
        "block_number":  12345,
        "timestamp":     1733270400,
        "confirmations": 10,
    }
    return mock_svc


@pytest.fixture
def mock_license_service(mock_transaction_service):
    return LicenseService(mock_transaction_service)


@pytest.fixture
def mock_multi_account_manager(blockchain_state):
    with patch(
        "apps.seed_licenses.services.multi_account_manager.multi_account_manager"
    ) as mock_mgr:
        mock_mgr.get_random_account.return_value     = blockchain_state.accounts[0]
        mock_mgr.get_account_by_address.return_value = blockchain_state.accounts[0]
        mock_mgr.get_accounts_info.return_value = [
            {
                "address": a["address"],
                "source":  a["source"],
                "index":   a["index"],
            }
            for a in blockchain_state.accounts
        ]
        yield mock_mgr


@pytest.fixture
def mock_event_parser():
    mock_parser = MagicMock()
    mock_parser.parse_and_store.return_value = (1, [])
    return mock_parser


@pytest.fixture
def mock_celery_tasks():
    with patch(
        "apps.seed_licenses.services.blockchain.tasks"
        ".process_transaction_confirmation.delay"
    ) as mock_task:
        mock_task.return_value = None
        yield mock_task