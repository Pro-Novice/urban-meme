import logging
from rest_framework.decorators import api_view, authentication_classes
from django.conf import settings

from Services.api_response import ApiResponse
from Services.exceptions import BlockchainError
from .services import BlockchainAPIService
from .authentication import APIKeyAuthentication, SSOAuthentication

logger = logging.getLogger(__name__)

# Initialize the service
blockchain_service = BlockchainAPIService()

# ── Admin Management APIs ─────────────────────────────────────

@api_view(["GET"])
@authentication_classes([APIKeyAuthentication])
def get_admin(request):
    """Get the current admin address for the smart contract"""
    try:
        admin_address = blockchain_service.get_admin()
        return ApiResponse(data={"admin_address": admin_address})
    except BlockchainError as exc:
        return ApiResponse(err=str(exc), status=400)
    except Exception as exc:
        logger.exception("Get admin error")
        return ApiResponse(err="Internal server error", status=500)

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
def change_admin(request):
    """
    Change the admin address for the smart contract
    Required fields: new_admin_address
    """
    new_admin_address = request.data.get('new_admin_address')

    if not new_admin_address:
        return ApiResponse(err="Missing required field: new_admin_address", status=400)

    try:
        result = blockchain_service.change_admin(new_admin_address)
        return ApiResponse(data=result, status=200)
    except BlockchainError as exc:
        return ApiResponse(err=str(exc), status=400)
    except Exception as exc:
        logger.exception("Change admin error")
        return ApiResponse(err="Internal server error", status=500)

# ── Officer Management APIs ─────────────────────────────────────

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
def add_department_officer(request):
    """
    Add a department officer to the smart contract
    Required fields: officer_address, role_id
    """
    officer_address = request.data.get('officer_address')
    role_id = request.data.get('role_id')

    if not officer_address or role_id is None:
        return ApiResponse(err="Missing required fields: officer_address, role_id", status=400)

    try:
        role_id = int(role_id)  # Convert to int if it's a string
        result = blockchain_service.add_department_officer(officer_address, role_id)
        return ApiResponse(data=result, status=201)
    except ValueError:
        return ApiResponse(err="role_id must be an integer", status=400)
    except BlockchainError as exc:
        return ApiResponse(err=str(exc), status=400)
    except Exception as exc:
        logger.exception("Add department officer error")
        return ApiResponse(err="Internal server error", status=500)

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
def remove_department_officer(request):
    """
    Remove a department officer from the smart contract
    Required fields: officer_address
    """
    officer_address = request.data.get('officer_address')

    if not officer_address:
        return ApiResponse(err="Missing required field: officer_address", status=400)

    try:
        result = blockchain_service.remove_department_officer(officer_address)
        return ApiResponse(data=result, status=200)
    except BlockchainError as exc:
        return ApiResponse(err=str(exc), status=400)
    except Exception as exc:
        logger.exception("Remove department officer error")
        return ApiResponse(err="Internal server error", status=500)

@api_view(["GET"])
@authentication_classes([APIKeyAuthentication])
def get_officer_role(request, officer_address):
    """Get the role of a department officer"""
    try:
        result = blockchain_service.get_officer_role(officer_address)
        return ApiResponse(data=result)
    except BlockchainError as exc:
        return ApiResponse(err=str(exc), status=400)
    except Exception as exc:
        logger.exception("Get officer role error")
        return ApiResponse(err="Internal server error", status=500)

@api_view(["GET"])
@authentication_classes([SSOAuthentication])
def get_current_officer_view(request):
    officer_info = request.auth  
    return ApiResponse(data=officer_info)

@api_view(["GET"])
@authentication_classes([APIKeyAuthentication])
def is_authorized_officer(request, officer_address):
    """Check if an address is an authorized officer"""
    try:
        result = blockchain_service.is_authorized_officer(officer_address)
        return ApiResponse(data=result)
    except BlockchainError as exc:
        return ApiResponse(err=str(exc), status=400)
    except Exception as exc:
        logger.exception("Check officer authorization error")
        return ApiResponse(err="Internal server error", status=500)

# ── Certificate Verification APIs ─────────────────────────────────────

@api_view(["GET"])
@authentication_classes([APIKeyAuthentication])
def generate_certificate_hash(request, license_id):
    """Generate a certificate hash for a license"""
    try:
        result = blockchain_service.generate_certificate_hash(license_id)
        return ApiResponse(data=result)
    except BlockchainError as exc:
        return ApiResponse(err=str(exc), status=400)
    except Exception as exc:
        logger.exception("Generate certificate hash error")
        return ApiResponse(err="Internal server error", status=500)

@api_view(["GET"])
@authentication_classes([APIKeyAuthentication])
def verify_certificate(request, license_id):
    """Verify a certificate for a license"""
    try:
        result = blockchain_service.verify_certificate(license_id)
        return ApiResponse(data=result)
    except BlockchainError as exc:
        return ApiResponse(err=str(exc), status=400)
    except Exception as exc:
        logger.exception("Verify certificate error")
        return ApiResponse(err="Internal server error", status=500)