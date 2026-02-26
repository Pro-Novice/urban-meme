import logging
from django.core.cache import cache  
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from utils.api_response import ApiResponse
from apps.seed_licenses.serializers import (
    SubmitLicenseApplicationSerializer,
    UpdateLicenseStatusSerializer,
    VerifyLicenseSerializer,
    UpdateLicenseDetailsSerializer,
    AddOfficerSerializer,
)
from apps.seed_licenses.services.license_service import LicenseService
from apps.seed_licenses.services.blockchain import TransactionService
from apps.seed_licenses.enums import LicenseStatusEnum

logger = logging.getLogger(__name__)


tx_service = TransactionService()
license_service = LicenseService(tx_service)


VALID_STATUS_TRANSITIONS = {
    LicenseStatusEnum.SUBMITTED.value: [LicenseStatusEnum.UNDER_REVIEW.value],
    LicenseStatusEnum.UNDER_REVIEW.value: [
        LicenseStatusEnum.DOCUMENTS_VERIFIED.value,
        LicenseStatusEnum.REJECTED.value,
    ],
    LicenseStatusEnum.DOCUMENTS_VERIFIED.value: [
        LicenseStatusEnum.INSPECTION_SCHEDULED.value,
    ],
    LicenseStatusEnum.INSPECTION_SCHEDULED.value: [
        LicenseStatusEnum.INSPECTION_COMPLETED.value,
    ],
    LicenseStatusEnum.INSPECTION_COMPLETED.value: [
        LicenseStatusEnum.APPROVED.value,
        LicenseStatusEnum.REJECTED.value,
    ],
    LicenseStatusEnum.APPROVED.value: [
        LicenseStatusEnum.REVOKED.value,
        LicenseStatusEnum.EXPIRED.value,
        LicenseStatusEnum.RENEWED.value,
    ],
    LicenseStatusEnum.REJECTED.value: [],
    LicenseStatusEnum.REVOKED.value: [],
    LicenseStatusEnum.EXPIRED.value: [LicenseStatusEnum.RENEWED.value],
    LicenseStatusEnum.RENEWED.value: [LicenseStatusEnum.EXPIRED.value, LicenseStatusEnum.REVOKED.value],
}

# --------------------------------------------------------------------
# 1️ Get Total License Count
# --------------------------------------------------------------------
@api_view(["GET"])
def check_total_license_count(request):
    """Retrieve total number of licenses created on blockchain."""
    try:
        count = license_service.get_total_count()
        return ApiResponse(data={"total_licenses": count}, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Error fetching total license count")
        return ApiResponse(err=f"Error fetching license count: {e}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# --------------------------------------------------------------------
# 2️ Submit License Application
# --------------------------------------------------------------------
@api_view(["POST"])
def submit_license_application(request):
    """Validate and submit a new license application to blockchain."""
    serializer = SubmitLicenseApplicationSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    try:
        result = license_service.submit_application(serializer.validated_data)
        return _create_response(result, license_number=serializer.validated_data["license_number"])
    except Exception as e:
        logger.exception("Submit license failed")
        return ApiResponse(err=f"Submit license failed: {e}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# --------------------------------------------------------------------
# 3️ Get License Basic Info
# --------------------------------------------------------------------
@api_view(["GET"])
def get_license_basic_info(request, license_number: str):
    """Retrieve basic license details by licenseNumber."""
    try:
        cache_key = f"license_basic_info_{license_number}"
        cached = cache.get(cache_key)
        if cached:
            logger.info("Cache hit: license %s", license_number)
            return ApiResponse(data=cached, status=HTTP_200_OK)

        data = license_service.get_basic_info(license_number)
        cache.set(cache_key, data, timeout=1800)
        
        return ApiResponse(data=data, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("License info fetch failed for %s", license_number)
        return ApiResponse(err=str(e), status=HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------------------------------------------------
# 4️ Get License QR Data
# --------------------------------------------------------------------
@api_view(["GET"])
def get_license_qr_data(request, license_number: str):
    """Retrieve QR-code verification data for a license."""
    try:
        cache_key = f"license_qr_data_{license_number}"
        cached = cache.get(cache_key)
        if cached:
            logger.info("Cache hit: QR data %s", license_number)
            return ApiResponse(data=cached, status=HTTP_200_OK)

        data = license_service.get_qr_data(license_number)
        cache.set(cache_key, data, timeout=1800)
        return ApiResponse(data=data, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("QR data fetch failed for %s", license_number)
        return ApiResponse(err=f"QR data fetch failed: {e}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# --------------------------------------------------------------------
# 5️ Get License Action History
# --------------------------------------------------------------------
@api_view(["GET"])
def get_license_action_history(request, license_number: str):
    """Retrieve all historical actions for a license."""
    try:
        data = license_service.get_action_history(license_number)
        return ApiResponse(data=data, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("History fetch failed for %s", license_number)
        return ApiResponse(err=str(e), status=HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------------------------------------------------
# 6️ Update License Status
# --------------------------------------------------------------------
@api_view(["POST"])
def update_license_status_view(request):
    """Update the lifecycle status of a license identified by licenseNumber."""
    serializer = UpdateLicenseStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    try:
        validated = serializer.validated_data
        result = license_service.update_status({
            "license_number":       validated["license_number"],
            "status":               validated["status"],
            "officer_name":         validated["officer_name"],
            "role":                 validated["role"],
            "remarks":              validated.get("remarks", ""),
            "renewal_period_days":  validated.get("renewal_period_days", 0),
            "valid_transitions":    VALID_STATUS_TRANSITIONS,
        })

        # Bust cache so next read reflects new status
        _invalidate_license_cache(validated["license_number"])

        return _tx_response(result)

    except ValueError as e:
        logger.warning("Status update rejected: %s", e)
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("License status update failed")
        return ApiResponse(err=f"License status update failed: {e}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# --------------------------------------------------------------------
# 7️ Verify License Document
# --------------------------------------------------------------------
@api_view(["POST"])
def verify_license_document(request):
    """Verify the integrity of a license document against its on-chain hash."""
    serializer = VerifyLicenseSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    try:
        result = license_service.verify_document(serializer.validated_data)
        return _tx_response(result)
    except Exception as e:
        logger.exception("License verification failed")
        return ApiResponse(err=f"License verification failed: {e}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# --------------------------------------------------------------------
# 8️ Update License Details
# --------------------------------------------------------------------
@api_view(["POST"])
def update_license_details(request):
    """Update mutable firm/crop fields on an existing license by licenseNumber."""
    serializer = UpdateLicenseDetailsSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    try:
        result = license_service.update_details(serializer.validated_data)
        _invalidate_license_cache(serializer.validated_data["license_number"])
        return _tx_response(result)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("License update failed")
        return ApiResponse(err=f"License update failed: {e}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# --------------------------------------------------------------------
# 9️ Add Officer to Contract
# --------------------------------------------------------------------
@api_view(["POST"])
def add_officer_to_contract(request):
    """Add a new officer to the contract's authorized callers list (admin only)."""
    serializer = AddOfficerSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    try:
        result = license_service.add_officer(serializer.validated_data)
        return _tx_response(result)
    except Exception as e:
        logger.exception("Add officer failed")
        return ApiResponse(err=f"Add officer failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _invalidate_license_cache(license_number: str) -> None:
    """Delete all cache entries associated with a licenseNumber."""
    cache.delete(f"license_basic_info_{license_number}")
    cache.delete(f"license_qr_data_{license_number}")
    logger.info("Cache invalidated for license %s", license_number)


def _create_response(result: dict, license_number: str):
    if not result.get("success", True):
        return ApiResponse(data=result, status=HTTP_400_BAD_REQUEST)

    return ApiResponse(
        data={
            "id":               license_number,        
            "status":           "SUCCESS",
            "message":          "License created successfully.",
            "transaction_hash": result.get("transaction_hash"),
            "sender_address":   result.get("sender_address"),
        },
        status=HTTP_202_ACCEPTED,
    )


def _tx_response(result: dict, include_sender_address=False):
    """Standardized response wrapper for blockchain transactions."""
    # If LicenseService returns "changed": False, handle no-op gracefully
    if result.get("changed") is False:
        return ApiResponse(
            data={
                "status": "no_change",
                "message": result.get("message", "No status change performed."),
            },
            status=HTTP_200_OK,
        )

    # If blockchain transaction failed
    if not result.get("success", True):
        return ApiResponse(data=result, status=HTTP_400_BAD_REQUEST)

    # Normal accepted blockchain transaction
    response_data = {
        "transaction_hash": result.get("transaction_hash"),
        "status": "accepted",
        "message": "Transaction submitted successfully.",
    }
    if include_sender_address and "sender_address" in result:
        response_data["sender_address"] = result["sender_address"]
    
    return ApiResponse(data=response_data, status=HTTP_202_ACCEPTED)