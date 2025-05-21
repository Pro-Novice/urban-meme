import base64
import json
import logging
from datetime import datetime
from typing import Any, Dict
from rest_framework.decorators import api_view
from django.utils.timezone import make_aware, now
from Services.api_response import ApiResponse
from Services.exceptions import BlockchainError
from seed_license.models import License
from ..seed_license_handler import SeedLicenseHandler
from django.utils.timezone import make_aware
logger = logging.getLogger(__name__)

_STATUS_LABELS = SeedLicenseHandler.STATUS_LABELS
def _ts_iso(ts: int | None) -> str | None:
    if ts and ts > 0:
        return make_aware(datetime.utcfromtimestamp(ts)).date().isoformat()
    return None


def _verification_payload(license_id: int) -> Dict[str, Any]:
    handler = SeedLicenseHandler()
    (
        license_id,
        _farmer_address,  
        _farmer_name,
        _location,
        _license_type_enum,
        _status_enum,
        _application_ts,
        _approval_ts,
        _expiry_ts,
        _is_active,
        _seed_details,
    ) = handler.get_license_summary(license_id)

    
    is_valid = handler.is_license_valid(license_id)

   
    try:
        db = License.objects.only("source").get(license_id=license_id)
        firm_name: str | None = db.source 
    except License.DoesNotExist:
        firm_name = None

   
    status_label: str = _STATUS_LABELS.get(_status_enum, "UNKNOWN")
    license_type_label: str = _license_type_enum if isinstance(_license_type_enum, str) else str(_license_type_enum)

   
    issue_date_raw = _approval_ts or _application_ts

    return {
        "license_id": str(license_id),
        "valid": is_valid,
        "status": status_label,
        "holder_name": _farmer_name,
        "firm_name": firm_name or _location or "",
        "license_type": license_type_label,
        "issue_date": _ts_iso(issue_date_raw),
        "expiry_date": _ts_iso(_expiry_ts),
        "verification_time": now().isoformat(),
    }



@api_view(["POST"])
def public_verify_license_view(request, license_id: str): 
    if "verification_code" not in request.data:
        return ApiResponse(err="verification_code required", status=400)

    try:
        data = _verification_payload(int(license_id))
        return ApiResponse(data=data, status=200)
    except BlockchainError as exc:
        return ApiResponse(err="License not found", code="LICENSE_NOT_FOUND", status=404)
    except Exception as exc:
        logger.exception("Verify by ID failed: %s", exc)
        return ApiResponse(err="Internal server error", status=500)

@api_view(["POST"])
def public_verify_qr_view(request): 
    raw = request.data.get("qr_data")
    if not raw:
        return ApiResponse(err="qr_data required", status=400)
    license_id: int | None = None
    if raw.isdigit():
        license_id = int(raw)
    else:
        try:
            decoded = base64.b64decode(raw).decode()
            obj = json.loads(decoded)
            license_id = int(obj.get("license_id"))
        except Exception:
            pass

    if license_id is None:
        return ApiResponse(err="Unsupported QR format", status=400)

    try:
        data = _verification_payload(license_id)
        return ApiResponse(data=data, status=200)
    except BlockchainError:
        return ApiResponse(err="License not found", code="LICENSE_NOT_FOUND", status=404)
    except Exception as exc:
        logger.exception("Verify via QR failed: %s", exc)
        return ApiResponse(err="Internal server error", status=500)

