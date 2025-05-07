import logging
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from web3 import Web3
from Services import logger
from .seed_license_handler import SeedLicenseHandler
from Services.api_response import BlockchainError
from Services.api_response import (
    SuccessResponse,
    ErrorResponse,
    ValidationErrorResponse,ApiResponse
)
from .permissions import (
    IsFarmer,
    IsAgricultureOfficer,
    IsDistrictCollector,
    IsSeedCertificationOfficer,
    IsSubsidyApprovalOfficer,
    IsQualityControlOfficer,
    IsAdmin
)



@api_view(['POST'])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated, IsFarmer])
def create_license(request):
    """
    Create a new seed license application
    """
    try:
        data = request.data
        required_fields = [
            'farmer_name', 'farmer_aadhaar', 'location', 'license_type',
            'seed_variety', 'crop_type', 'quantity', 'quality_parameters', 'source'
        ]

        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return ValidationErrorResponse(
                message="Missing required fields",
                errors={'missing_fields': missing_fields}
            )

        handler = SeedLicenseHandler()
        tx = handler.apply_for_license(
            data['farmer_name'],
            data['farmer_aadhaar'],
            data['location'],
            data['license_type'],
            data['seed_variety'],
            data['crop_type'],
            int(data['quantity']),
            data['quality_parameters'],
            data['source'],
            request.user.blockchain_address
        )

        return SuccessResponse(
            data={'transaction': tx},
            message="License application submitted successfully",
            status_code=status.HTTP_201_CREATED
        )

    except BlockchainError as e:
        return ErrorResponse(
            message="Blockchain error",
            errors=str(e),
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Create license error: {str(e)}", exc_info=True)
        return ErrorResponse(
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated])
def update_license_status(request, license_id):
    """
    Update license status (for authorized officers)
    """
    try:
        # Check permissions based on role
        if not any([
            request.user.is_agriculture_officer,
            request.user.is_district_collector,
            request.user.is_seed_certification_officer,
            request.user.is_subsidy_approval_officer,
            request.user.is_quality_control_officer,
            request.user.is_admin
        ]):
            return ErrorResponse(
                message="Unauthorized - Officer role required",
                status_code=status.HTTP_403_FORBIDDEN
            )

        data = request.data
        required_fields = ['new_status', 'remarks']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            return ValidationErrorResponse(
                message="Missing required fields",
                errors={'missing_fields': missing_fields}
            )

        # Get attached documents hash if provided
        attached_docs_hash = data.get('attached_docs_hash', b'')

        handler = SeedLicenseHandler()
        tx = handler.update_license_status(
            int(license_id),
            data['new_status'],
            data['remarks'],
            attached_docs_hash,
            request.user.blockchain_address
        )

        return SuccessResponse(
            data={'transaction': tx},
            message="License status updated successfully"
        )

    except BlockchainError as e:
        return ErrorResponse(
            message="Blockchain error",
            errors=str(e),
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Update license status error: {str(e)}", exc_info=True)
        return ErrorResponse(
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@parser_classes([JSONParser])
def get_license(request, license_id):
    """
    Get license details (public access)
    """
    try:
        handler = SeedLicenseHandler()
        license_data = handler.get_license_summary(int(license_id))

        return SuccessResponse(
            data={'license': license_data},
            message="License details retrieved successfully"
        )

    except BlockchainError as e:
        return ErrorResponse(
            message="Blockchain error",
            errors=str(e),
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Get license error: {str(e)}", exc_info=True)
        return ErrorResponse(
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@parser_classes([JSONParser])
def verify_license(request, license_id):
    """
    Verify license validity (public access)
    """
    try:
        handler = SeedLicenseHandler()
        is_valid, license_type, farmer_name, approval_date, expiry_date = handler.verify_certificate(int(license_id))

        return SuccessResponse(
            data={
                'is_valid': is_valid,
                'license_type': license_type,
                'farmer_name': farmer_name,
                'approval_date': approval_date,
                'expiry_date': expiry_date
            },
            message="License verification completed"
        )

    except BlockchainError as e:
        return ErrorResponse(
            message="Blockchain error",
            errors=str(e),
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Verify license error: {str(e)}", exc_info=True)
        return ErrorResponse(
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated])
def get_certificate_hash(request, license_id):
    """
    Get certificate hash for QR code generation
    """
    try:
        handler = SeedLicenseHandler()
        certificate_hash = handler.generate_certificate_hash(int(license_id))

        return SuccessResponse(
            data={'certificate_hash': certificate_hash.hex()},
            message="Certificate hash generated successfully"
        )

    except BlockchainError as e:
        return ErrorResponse(
            message="Blockchain error",
            errors=str(e),
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Get certificate hash error: {str(e)}", exc_info=True)
        return ErrorResponse(
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated, IsAdmin])
def add_officer(request):
    """
    Add new department officer (admin only)
    """
    try:
        data = request.data
        required_fields = ['officer_address', 'role']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            return ValidationErrorResponse(
                message="Missing required fields",
                errors={'missing_fields': missing_fields}
            )

        # Validate Ethereum address
        if not Web3.is_address(data['officer_address']):
            return ValidationErrorResponse(
                message="Invalid Ethereum address",
                errors={'officer_address': 'Must be a valid Ethereum address'}
            )

        handler = SeedLicenseHandler()
        tx = handler.add_department_officer(
            data['officer_address'],
            data['role'],
            request.user.blockchain_address
        )

        return SuccessResponse(
            data={'transaction': tx},
            message="Officer added successfully",
            status_code=status.HTTP_201_CREATED
        )

    except BlockchainError as e:
        return ErrorResponse(
            message="Blockchain error",
            errors=str(e),
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Add officer error: {str(e)}", exc_info=True)
        return ErrorResponse(
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@parser_classes([JSONParser])
@permission_classes([IsAuthenticated, IsAdmin])
def remove_officer(request):
    """
    Remove department officer (admin only)
    """
    try:
        data = request.data
        if 'officer_address' not in data:
            return ValidationErrorResponse(
                message="Missing required field",
                errors={'missing_field': 'officer_address'}
            )

        # Validate Ethereum address
        if not Web3.is_address(data['officer_address']):
            return ValidationErrorResponse(
                message="Invalid Ethereum address",
                errors={'officer_address': 'Must be a valid Ethereum address'}
            )

        handler = SeedLicenseHandler()
        tx = handler.remove_department_officer(
            data['officer_address'],
            request.user.blockchain_address
        )

        return SuccessResponse(
            data={'transaction': tx},
            message="Officer removed successfully"
        )

    except BlockchainError as e:
        return ErrorResponse(
            message="Blockchain error",
            errors=str(e),
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Remove officer error: {str(e)}", exc_info=True)
        return ApiResponse(
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )