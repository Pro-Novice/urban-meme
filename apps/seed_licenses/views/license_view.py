import logging
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
)
from apps.seed_licenses.services.license_service import LicenseService
from apps.seed_licenses.services.blockchain import TransactionService
from apps.seed_licenses.enums import LicenseStatusEnum

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Dependency Injection (SOLID: Dependency Inversion)
# --------------------------------------------------------------------
tx_service = TransactionService()
license_service = LicenseService(tx_service)

# --------------------------------------------------------------------
# License Status Transitions (Business Workflow Rules)
# --------------------------------------------------------------------
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
# 1️⃣ Get Total License Count
# --------------------------------------------------------------------
@api_view(["GET"])
def check_total_license_count(request):
    """Retrieve total number of licenses created on blockchain."""
    try:
        count = tx_service.read("licenseIdCounter", [])
        return ApiResponse(data={"total_licenses": count}, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Error fetching total license count")
        return ApiResponse(
            err=f"Error fetching license count: {e}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )

# --------------------------------------------------------------------
# 2️⃣ Submit License Application
# --------------------------------------------------------------------
@api_view(["POST"])
def submit_license_application(request):
    """Validate and submit a new license application to blockchain."""
    serializer = SubmitLicenseApplicationSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    try:
        result = license_service.submit_application(serializer.validated_data)
        return _tx_response(result)
    except Exception as e:
        logger.exception("Submit license failed")
        return ApiResponse(
            err=f"Submit license failed: {e}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )

# --------------------------------------------------------------------
# 3️⃣ Get License Basic Info
# --------------------------------------------------------------------
@api_view(["GET"])
def get_license_basic_info(request, license_id: int):
    """Retrieve basic license details by license ID."""
    try:
        data = license_service.get_basic_info(int(license_id))
        return ApiResponse(data=data, status=HTTP_200_OK)
    except ValueError:
        return ApiResponse(err="License ID must be an integer.", status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception(f"License info fetch failed for ID {license_id}")
        return ApiResponse(err=str(e), status=HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------------------------------------------------
# 4️⃣ Get License QR Data
# --------------------------------------------------------------------
@api_view(["GET"])
def get_license_qr_data(request, license_id: int):
    """Retrieve QR-code verification data for a license."""
    try:
        license_id = int(license_id)
        data = license_service.get_qr_data(license_id)
        return ApiResponse(data=data, status=HTTP_200_OK)
    except ValueError:
        return ApiResponse(err="License ID must be an integer.", status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception(f"QR data fetch failed for license ID {license_id}")
        return ApiResponse(
            err=f"QR data fetch failed: {e}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )

# --------------------------------------------------------------------
# 5️⃣ Get License Action History
# --------------------------------------------------------------------
@api_view(["GET"])
def get_license_action_history(request, license_id: int):
    """Retrieve historical actions performed on a license."""
    try:
        data = license_service.get_action_history(int(license_id))
        return ApiResponse(data=data, status=HTTP_200_OK)
    except ValueError:
        return ApiResponse(err="License ID must be an integer.", status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception(f"License history fetch failed for ID {license_id}")
        return ApiResponse(err=str(e), status=HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------------------------------------------------
# 6️⃣ Update License Status
# --------------------------------------------------------------------
@api_view(["POST"])
def update_license_status_view(request):
    """Update the status of a license (e.g., REVIEW → APPROVED)."""
    serializer = UpdateLicenseStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    try:
        validated = serializer.validated_data
        payload = {
            "license_id": validated["license_id"],
            "status": validated["status"],  # returns int now
            "officer_name": validated["officer_name"],
            "role": validated["role"],
            "remarks": validated.get("remarks", ""),
            "renewal_period_days": validated.get("renewal_period_days", 0),
            "valid_transitions": VALID_STATUS_TRANSITIONS,
        }

        result = license_service.update_status(payload)
        return _tx_response(result)

    except ValueError as e:
        # raised from service when invalid transition
        logger.warning("Invalid transition attempted: %s", e)
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("License status update failed")
        return ApiResponse(
            err=f"License status update failed: {e}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )

# --------------------------------------------------------------------
# 7️⃣ Verify License Document
# --------------------------------------------------------------------
@api_view(["POST"])
def verify_license_document(request):
    """Verify the integrity and validity of a license document."""
    serializer = VerifyLicenseSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    try:
        result = license_service.verify_document(serializer.validated_data)
        return _tx_response(result)
    except Exception as e:
        logger.exception("License verification failed")
        return ApiResponse(
            err=f"License verification failed: {e}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )

# --------------------------------------------------------------------
# 8️⃣ Update License Details
# --------------------------------------------------------------------
@api_view(["POST"])
def update_license_details(request):
    """Update firm/crop details for an existing license."""
    serializer = UpdateLicenseDetailsSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    try:
        result = license_service.update_details(serializer.validated_data)
        return _tx_response(result)
    except Exception as e:
        logger.exception("License update failed")
        return ApiResponse(
            err=f"License update failed: {e}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )

# --------------------------------------------------------------------
# Helper Function: Uniform Transaction Response
# --------------------------------------------------------------------
def _tx_response(result: dict):
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
    return ApiResponse(
        data={
            "transaction_hash": result.get("transaction_hash"),
            "status": "accepted",
            "message": "Transaction submitted successfully.",
        },
        status=HTTP_202_ACCEPTED,
    )
