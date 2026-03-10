import logging
from django.core.cache import cache  
from django.db import IntegrityError, transaction
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
from apps.seed_licenses.models import LicenseSubmission, EventLog
from apps.seed_licenses.schemas import (
    license_count_schema, submit_license_schema, license_basic_info_schema,
    license_history_schema, license_qr_schema, update_status_schema,
    verify_document_schema, update_details_schema, add_officer_schema,
    license_basic_info_by_number_schema, license_history_by_number_schema
)

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
# 1️ Get Total License Count
# --------------------------------------------------------------------
@license_count_schema()
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
# 2️ Submit License Application
# --------------------------------------------------------------------
@submit_license_schema()
@api_view(["POST"])
def submit_license_application(request):
    """Validate and submit a new license application to blockchain."""
    serializer = SubmitLicenseApplicationSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    license_number = serializer.validated_data["license_number"]

    try:
        with transaction.atomic():
            LicenseSubmission.objects.create(license_number=license_number)
    except IntegrityError:
        return ApiResponse(err="License number already exists.", status=HTTP_400_BAD_REQUEST)

    try:
        result = license_service.submit_application(serializer.validated_data)
        if result.get("success") is False:
            LicenseSubmission.objects.filter(license_number=license_number).delete()
        else:
            tx_hash = result.get("transaction_hash")
            if tx_hash:
                LicenseSubmission.objects.filter(license_number=license_number).update(
                    transaction_hash=tx_hash
                )
        return _tx_response(
            result,
            include_sender_address=True,
            extra_data={"license_number": license_number},
        )
    except Exception as e:
        LicenseSubmission.objects.filter(license_number=license_number).delete()
        logger.exception("Submit license failed")
        return ApiResponse(
            err=f"Submit license failed: {e}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )

# --------------------------------------------------------------------
# 3️ Get License Basic Info
# --------------------------------------------------------------------
@license_basic_info_schema()
@api_view(["GET"])
def get_license_basic_info(request, license_id: int):
    """Retrieve basic license details by license ID."""
    try:

        cache_key = f"license_basic_info_{license_id}"
        
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Cache hit for license {license_id}")
            return ApiResponse(data=cached_data, status=HTTP_200_OK)

        logger.info(f"Cache miss for license {license_id}, reading from blockchain")
        data = license_service.get_basic_info((license_id))
        data = _override_license_number(data, license_id)
        

        cache.set(cache_key, data, timeout=1800)
        
        return ApiResponse(data=data, status=HTTP_200_OK)
    except ValueError:
        return ApiResponse(err="License ID must be an integer.", status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception(f"License info fetch failed for ID {license_id}")
        return ApiResponse(err=str(e), status=HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------------------------------------------------
# 3.1️ Get License Basic Info By License Number
# --------------------------------------------------------------------
@license_basic_info_by_number_schema()
@api_view(["GET"])
def get_license_basic_info_by_number(request, license_number: str):
    """Retrieve basic license details by license number."""
    try:
        license_number = (license_number or "").strip()
        if not license_number:
            return ApiResponse(err="License number cannot be empty.", status=HTTP_400_BAD_REQUEST)

        cache_key = f"license_basic_info_by_number_{license_number}"
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Cache hit for license number {license_number}")
            return ApiResponse(data=cached_data, status=HTTP_200_OK)

        submission = LicenseSubmission.objects.filter(license_number=license_number).first()
        if submission and submission.license_id:
            data = license_service.get_basic_info(submission.license_id)
            data = _override_license_number(data, submission.license_id)
            cache.set(cache_key, data, timeout=1800)
            return ApiResponse(data=data, status=HTTP_200_OK)

        if submission and submission.transaction_hash and not submission.license_id:
            _try_attach_license_id(submission)
            if submission.license_id:
                data = license_service.get_basic_info(submission.license_id)
                data = _override_license_number(data, submission.license_id)
                cache.set(cache_key, data, timeout=1800)
                return ApiResponse(data=data, status=HTTP_200_OK)

        return ApiResponse(
            err="License number not found yet. Please try again later.",
            status=HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.exception(f"License info fetch failed for number {license_number}")
        return ApiResponse(err=str(e), status=HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------------------------------------------------
# 4️ Get License QR Data
# --------------------------------------------------------------------
@license_qr_schema()
@api_view(["GET"])
def get_license_qr_data(request, license_id: int):
    """Retrieve QR-code verification data for a license."""
    try:
        license_id = int(license_id)
        

        cache_key = f"license_qr_data_{license_id}"
        

        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Cache hit for QR data {license_id}")
            return ApiResponse(data=cached_data, status=HTTP_200_OK)
        
 
        logger.info(f"Cache miss for QR data {license_id}")
        data = license_service.get_qr_data(license_id)
        
        cache.set(cache_key, data, timeout=1800)
        
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
# 5️ Get License Action History
# --------------------------------------------------------------------
@license_history_schema()
@api_view(["GET"])
def get_license_action_history(request, license_id: int):
    """Retrieve historical actions performed on a license."""
    try:
        history = license_service.get_action_history(int(license_id))
        license_number = _resolve_license_number(license_id=license_id)
        return ApiResponse(
            data={
                "licenseNumber": license_number,
                "history": history,
            },
            status=HTTP_200_OK,
        )
    except ValueError:
        return ApiResponse(err="License ID must be an integer.", status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception(f"License history fetch failed for ID {license_id}")
        return ApiResponse(err=str(e), status=HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------------------------------------------------
# 5.1️ Get License Action History By License Number
# --------------------------------------------------------------------
@license_history_by_number_schema()
@api_view(["GET"])
def get_license_action_history_by_number(request, license_number: str):
    """Retrieve historical actions by license number."""
    try:
        license_number = (license_number or "").strip()
        if not license_number:
            return ApiResponse(err="License number cannot be empty.", status=HTTP_400_BAD_REQUEST)

        submission = LicenseSubmission.objects.filter(license_number=license_number).first()
        if submission and submission.license_id:
            history = license_service.get_action_history(int(submission.license_id))
            return ApiResponse(
                data={
                    "licenseNumber": license_number,
                    "history": history,
                },
                status=HTTP_200_OK,
            )

        if submission and submission.transaction_hash and not submission.license_id:
            _try_attach_license_id(submission)
            if submission.license_id:
                history = license_service.get_action_history(int(submission.license_id))
                return ApiResponse(
                    data={
                        "licenseNumber": license_number,
                        "history": history,
                    },
                    status=HTTP_200_OK,
                )

        return ApiResponse(
            err="License number not found yet. Please try again later.",
            status=HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.exception(f"License history fetch failed for number {license_number}")
        return ApiResponse(err=str(e), status=HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _try_attach_license_id(submission: LicenseSubmission) -> None:
    """Attach license_id from EventLog if available for the submission tx hash."""
    if not submission.transaction_hash or submission.license_id:
        return
    log = (
        EventLog.objects.filter(transaction_hash=submission.transaction_hash)
        .order_by("timestamp")
        .first()
    )
    if log and log.license_id:
        submission.license_id = log.license_id
        submission.save(update_fields=["license_id"])


def _override_license_number(data: dict, license_id: int) -> dict:
    """Override blockchain licenseNumber with submitted one and hide licenseId."""
    if not isinstance(data, dict):
        return data

    submission = LicenseSubmission.objects.filter(license_id=license_id).first()
    if not submission:
        log = EventLog.objects.filter(license_id=license_id).order_by("timestamp").first()
        if log:
            submission = LicenseSubmission.objects.filter(transaction_hash=log.transaction_hash).first()
            if submission and not submission.license_id:
                submission.license_id = license_id
                submission.save(update_fields=["license_id"])

    if submission and submission.license_number:
        data["licenseNumber"] = submission.license_number

    data.pop("licenseId", None)
    return data


def _resolve_license_id_from_number(license_number: str) -> int:
    """Resolve license_id from submitted license_number."""
    if not license_number:
        return None
    submission = LicenseSubmission.objects.filter(license_number=license_number).first()
    if submission:
        if not submission.license_id:
            _try_attach_license_id(submission)
        if submission.license_id:
            return submission.license_id
    return None


def _resolve_license_number(license_id: int) -> str:
    """Resolve submitted license number for a license_id, fallback to blockchain."""
    submission = LicenseSubmission.objects.filter(license_id=license_id).first()
    if submission and submission.license_number:
        return submission.license_number

    log = EventLog.objects.filter(license_id=license_id).order_by("timestamp").first()
    if log:
        submission = LicenseSubmission.objects.filter(transaction_hash=log.transaction_hash).first()
        if submission and submission.license_number:
            if not submission.license_id:
                submission.license_id = license_id
                submission.save(update_fields=["license_id"])
            return submission.license_number

    try:
        data = license_service.get_basic_info(int(license_id))
        if isinstance(data, dict):
            return data.get("licenseNumber")
    except Exception:
        return None

    return None

# --------------------------------------------------------------------
# 6️ Update License Status
# --------------------------------------------------------------------
@update_status_schema()
@api_view(["POST"])
def update_license_status_view(request):
    """Update the status of a license (e.g., REVIEW → APPROVED)."""
    serializer = UpdateLicenseStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    try:
        validated = serializer.validated_data
        license_id = validated.get("license_id")
        license_number = validated.get("license_number")

        if not license_id and license_number:
            license_id = _resolve_license_id_from_number(license_number)
            if not license_id:
                return ApiResponse(
                    err="License number not found yet. Please try again later.",
                    status=HTTP_400_BAD_REQUEST,
                )

        payload = {
            "license_id": license_id,
            "status": validated["status"],  # returns int now
            "officer_name": validated["officer_name"],
            "role": validated["role"],
            "remarks": validated.get("remarks", ""),
            "renewal_period_days": validated.get("renewal_period_days", 0),
            "valid_transitions": VALID_STATUS_TRANSITIONS,
        }

        result = license_service.update_status(payload)
        
        cache.delete(f"license_basic_info_{license_id}")
        cache.delete(f"license_qr_data_{license_id}")
        submission = LicenseSubmission.objects.filter(license_id=license_id).first()
        if submission and submission.license_number:
            cache.delete(f"license_basic_info_by_number_{submission.license_number}")

        logger.info(f"Cache invalidated for license {license_id}")
        
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
# 7️ Verify License Document
# --------------------------------------------------------------------
@verify_document_schema()
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
# 8️ Update License Details
# --------------------------------------------------------------------
@update_details_schema()
@api_view(["POST"])
def update_license_details(request):
    """Update firm/crop details for an existing license."""
    serializer = UpdateLicenseDetailsSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    try:
        result = license_service.update_details(serializer.validated_data)
        

        license_id = serializer.validated_data.get("license_id")
        if license_id:
            cache.delete(f"license_basic_info_{license_id}")
            cache.delete(f"license_qr_data_{license_id}")
            submission = LicenseSubmission.objects.filter(license_id=license_id).first()
            if submission and submission.license_number:
                cache.delete(f"license_basic_info_by_number_{submission.license_number}")
                logger.info(f"Cache invalidated for license number {submission.license_number}")

            logger.info(f"Cache invalidated for license {license_id}")
        
        return _tx_response(result)
    except Exception as e:
        logger.exception("License update failed")
        return ApiResponse(
            err=f"License update failed: {e}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )

# --------------------------------------------------------------------
# 9️ Add Officer to Contract
# --------------------------------------------------------------------
@add_officer_schema()
@api_view(["POST"])
def add_officer_to_contract(request):
    """
    Add a new officer to the authorized callers list.
    Only the admin wallet can perform this action.
    """
    serializer = AddOfficerSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    try:
        result = license_service.add_officer(serializer.validated_data)
        return _tx_response(result)  

    except Exception as e:
        logger.exception("Add officer failed")
        return ApiResponse(err=f"Add officer failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)
    
# --------------------------------------------------------------------
# Helper Function: Uniform Transaction Response
# --------------------------------------------------------------------
def _tx_response(result: dict, include_sender_address=False, extra_data=None):
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
    if extra_data:
        response_data.update(extra_data)
    
    return ApiResponse(data=response_data, status=HTTP_202_ACCEPTED)
