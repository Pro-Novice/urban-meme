import json, hashlib, logging
from datetime import datetime
from rest_framework import status
from django.utils.timezone import make_aware
from django_redis import get_redis_connection
from rest_framework.decorators import api_view, authentication_classes
from Services.api_response import ApiResponse
from Services.exceptions import BlockchainError
from seed_license.blockchain_api.authentication import APIKeyAuthentication   
from seed_license.seed_license_handler import SeedLicenseHandler

logger = logging.getLogger(__name__)

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
def public_verify_license_view(request, license_id: int):

    try:
        valid, ltype, farmer, appr, exp = SeedLicenseHandler().verify_certificate(license_id)
        return ApiResponse(data={
            "license_id":       license_id,
            "is_valid":         bool(valid),
            "license_type":     ltype,
            "farmer_name":      farmer,
            "approval_date":    datetime.fromtimestamp(appr) if appr else None,
            "expiry_date":      datetime.fromtimestamp(exp) if exp else None,
        })
    except BlockchainError as exc:
        return ApiResponse(err=str(exc), status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:                      
        return ApiResponse(err=str(exc), status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
def public_verify_qr_view(request):

    redis_id = request.data.get("redis_id")
    if not redis_id:
        return ApiResponse(err="redis_id missing", status=status.HTTP_404_NOT_FOUND)

    r = get_redis_connection("default")
    payload = r.get(redis_id)
    if not payload:
        return ApiResponse(err="QR credential expired or invalid", status=status.HTTP_404_NOT_FOUND)

    data = json.loads(payload)
    license_id      = data["license_id"]
    expected_hash   = bytes.fromhex(data["certificate_hash"])

    chain_hash = SeedLicenseHandler().generate_certificate_hash(license_id)
    status_code = "VERIFIED" if chain_hash == expected_hash else "NOT_VERIFIED"

    return ApiResponse(data={
        "status":           status_code,
        "license_id":       license_id,
        "certificate_hash": hashlib.sha256(payload).hexdigest(),  
        "on_chain_hash":    chain_hash.hex(),
        "license_holder":   data["farmer_name"],
        "issued_on":        data["approval_date"],
    }, status=status.HTTP_201_CREATED if status_code == "VERIFIED" else 403)
