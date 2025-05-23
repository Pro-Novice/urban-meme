"""Views for handling Raj Kisan Officer registration, listing, detail, update, and deletion."""
import hashlib
import json
from datetime import datetime
from django.utils import timezone
from django.core.files.storage import default_storage
from django.contrib.messages.storage import default_storage
from django.db.models import Q, Count
from django.forms.models import model_to_dict
from pydantic.v1 import ValidationError
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from web3 import Web3
from Services.api_response import ApiResponse
from Services.logger import logger
from django.core.paginator import Paginator, EmptyPage
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator
from datetime import timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
import calendar
from collections import defaultdict
from django.forms.models import model_to_dict
from rest_framework.decorators import api_view
from rest_framework import status
from seed_license.blockchain_api.authentication import APIKeyAuthentication
from seed_license.blockchain_api.services import BlockchainAPIService
from seed_license.models import License, BlockchainTransaction
from seed_license.seed_license_handler import SeedLicenseHandler
from .models import RajOfficer
from .serializer import RajasthanOfficerSerializer
import logging


@api_view(['POST'])
@authentication_classes([APIKeyAuthentication])
def register_raj_kisan_officer(request):
    """Registers a new Raj Kisan officer with blockchain integration."""
    logger.info("Officer registration request data: %s", request.data)
    serializer = RajasthanOfficerSerializer(data=request.data)

    if not serializer.is_valid():
        logger.warning("Invalid officer data: %s", serializer.errors)
        return ApiResponse(err=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Initialize blockchain service
        blockchain_service = BlockchainAPIService()
        #
        # # Verify requesting user is admin
        # if not request.user.is_superuser:
        #     return ApiResponse(
        #         err="Only admin users can register officers",
        #         status=status.HTTP_403_FORBIDDEN
        #     )

        # Save officer to database first
        officer = serializer.save()
        logger.info("Officer saved to database: %s", officer.user_id)

        # Add to blockchain if address provided
        if officer.blockchain_address:
            result = blockchain_service.add_department_officer(
                officer_address=officer.blockchain_address,
                role_id=officer.role
            )

            logger.info(
                "Officer added to blockchain",
                extra={
                    'officer_id': officer.user_id,
                    'tx_hash': result['transaction_hash']
                }
            )

        return ApiResponse(
            data=serializer.data,
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        logger.error("Officer registration failed: %s", str(e), exc_info=True)
        # Rollback DB creation if blockchain fails
        if 'officer' in locals():
            officer.delete()
        return ApiResponse(
            err="Officer registration failed",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
def list_all_raj_kisan_officers(request):
    """Returns a list of all Raj Kisan officers with blockchain verification."""
    try:
        officers = RajOfficer.objects.all()
        serializer = RajasthanOfficerSerializer(officers, many=True)
        officer_data = serializer.data

        # Initialize blockchain service
        blockchain_service = BlockchainAPIService()

        # Verify each officer against blockchain
        for officer in officer_data:
            if officer.get('blockchain_address'):
                try:
                    verification = blockchain_service.is_authorized_officer(
                        officer['blockchain_address']
                    )
                    officer['blockchain_verified'] = verification['is_authorized']
                except Exception:
                    officer['blockchain_verified'] = False
            else:
                officer['blockchain_verified'] = False

        return ApiResponse(
            data=officer_data,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error("Failed to fetch officers list: %s", str(e), exc_info=True)
        return ApiResponse(
            err="Failed to retrieve officers",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
def get_raj_kisan_officer_detail(request, officer_id):
    """Returns details of a specific officer with blockchain verification."""
    try:
        officer = RajOfficer.objects.get(user_id=officer_id)
        serializer = RajasthanOfficerSerializer(officer)
        data = serializer.data

        # Initialize blockchain service
        blockchain_service = BlockchainAPIService()

        # Add blockchain verification details if address exists
        if officer.blockchain_address:
            try:
                # Check authorization
                verification = blockchain_service.is_authorized_officer(
                    officer.blockchain_address
                )
                data['blockchain_verified'] = verification['is_authorized']

                # Get role details
                role_info = blockchain_service.get_officer_role(
                    officer.blockchain_address
                )
                data['blockchain_role'] = role_info['role_name']
            except Exception:
                data['blockchain_verified'] = False

        return ApiResponse(
            data=data,
            status=status.HTTP_200_OK
        )

    except RajOfficer.DoesNotExist:
        return ApiResponse(
            err="Officer not found",
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(
            "Failed to fetch officer details: %s",
            str(e),
            exc_info=True
        )
        return ApiResponse(
            err="Failed to retrieve officer details",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT'])
@authentication_classes([APIKeyAuthentication])
def update_raj_kisan_officer(request, officer_id):
    """Updates details of an existing officer with blockchain sync."""
    try:
        officer = RajOfficer.objects.get(user_id=officer_id)
    except RajOfficer.DoesNotExist:
        return ApiResponse(
            err="Officer not found",
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = RajasthanOfficerSerializer(officer, data=request.data, partial=True)
    if not serializer.is_valid():
        return ApiResponse(
            err=serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Initialize blockchain service
        blockchain_service = BlockchainAPIService()

        # Check if requesting user is admin
        if not request.user.is_superuser:
            return ApiResponse(
                err="Only admin users can update officers",
                status=status.HTTP_403_FORBIDDEN
            )

        old_blockchain_address = officer.blockchain_address
        updated_officer = serializer.save()

        # Handle blockchain updates if address or role changed
        if updated_officer.blockchain_address and (
                'blockchain_address' in request.data or
                'role' in request.data
        ):
            # Remove old address if it exists and is different
            if old_blockchain_address and old_blockchain_address != updated_officer.blockchain_address:
                blockchain_service.remove_department_officer(old_blockchain_address)

            # Add new address
            result = blockchain_service.add_department_officer(
                officer_address=updated_officer.blockchain_address,
                role_id=updated_officer.role
            )

            logger.info(
                "Officer blockchain record updated",
                extra={
                    'officer_id': officer_id,
                    'tx_hash': result['transaction_hash']
                }
            )

        return ApiResponse(
            data=serializer.data,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(
            "Failed to update officer: %s",
            str(e),
            exc_info=True
        )
        return ApiResponse(
            err="Failed to update officer",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@authentication_classes([APIKeyAuthentication])
def delete_raj_kisan_officer(request):
    """Deletes an officer by user ID and removes from blockchain."""
    try:
        officer_id= request.query_params.get('id')
        officer = RajOfficer.objects.get(user_id=officer_id)
    except RajOfficer.DoesNotExist:
        return ApiResponse(
            err="Officer not found",
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        # Initialize blockchain service
        blockchain_service = BlockchainAPIService()


        # Remove from blockchain if address exists
        if officer.blockchain_address:
            result = blockchain_service.remove_department_officer(
                officer.blockchain_address
            )
            logger.info(
                "Officer removed from blockchain",
                extra={
                    'officer_id': officer_id,
                    'tx_hash': result['transaction_hash']
                }
            )

        # Delete from database
        officer.delete()
        logger.info("Officer deleted from database: %s", officer_id)

        return ApiResponse(
            data="Officer deleted successfully",
            status=status.HTTP_204_NO_CONTENT
        )

    except Exception as e:
        logger.error(
            "Failed to delete officer: %s",
            str(e),
            exc_info=True
        )
        return ApiResponse(
            err="Failed to delete officer",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
def department_licenses_view(request):
    """
    License list view using DB with filters and pagination.
    Query Params: page, limit, status, type, district, from_date, to_date
    """
    try:
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 10))
        status_filter = request.query_params.get('status')
        type_filter = request.query_params.get('type')
        district_filter = request.query_params.get('district')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')

        qs = License.objects.all().order_by('-submitted_at')

        if status_filter:
            qs = qs.filter(status=status_filter)
        if type_filter:
            qs = qs.filter(license_type=type_filter)
        if district_filter:
            qs = qs.filter(location__icontains=district_filter)
        if from_date:
            try:
                from_dt = datetime.strptime(from_date, '%Y-%m-%d')
                qs = qs.filter(submitted_at__date__gte=from_dt)
            except Exception as e:
                logger.warning(f"Invalid from_date format: {from_date}")
        if to_date:
            try:
                to_dt = datetime.strptime(to_date, '%Y-%m-%d')
                qs = qs.filter(submitted_at__date__lte=to_dt)
            except Exception as e:
                logger.warning(f"Invalid to_date format: {to_date}")

        paginator = Paginator(qs, limit)
        page_obj = paginator.get_page(page)

        licenses_data = [{
            'id': lic.license_id,
            'location': lic.location,
            'applicant_name':lic.applicant,
            'license_type': lic.license_type,
            'status': lic.status,
            'application_date': lic.submitted_at.isoformat() if lic.submitted_at else None,
            'seed_details': {
                'seed_variety': lic.seed_variety,
                'crop_type': lic.crop_type,
                'quality_parameters': lic.quality_parameters,
            }
        } for lic in page_obj.object_list]

        return ApiResponse(data={
            'total': paginator.count,
            'page': page,
            'limit': limit,
            'licenses': licenses_data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in license_list_view: {str(e)}")
        return ApiResponse(err=f'Failed to fetch licenses. Details: {str(e)}', status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@authentication_classes([APIKeyAuthentication])
def department_license_detail_view(request):
    try:
        license_id = request.query_params.get("id")

        if not license_id:
            return ApiResponse(err="Missing required query parameter: 'id'", status=status.HTTP_400_BAD_REQUEST)

        try:
            license_id = int(license_id)
        except ValueError:
            return ApiResponse(err="License ID must be a valid integer", status=status.HTTP_400_BAD_REQUEST)

        handler = SeedLicenseHandler()

        try:
            summary = handler.get_license_summary(license_id)
        except ValidationError as ve:
            logger.warning(f"Validation error fetching license summary: {ve}")
            return ApiResponse(err="Invalid license data: " + str(ve), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error in SeedLicenseHandler.get_license_summary")
            return ApiResponse(err=f"Failed to retrieve license summary, {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not summary:
            return ApiResponse(err="No license data found for the given ID", status=status.HTTP_404_NOT_FOUND)

        return ApiResponse(data={
            "license_id": summary[0],
            "farmer_address": summary[1],
            "name": summary[2],
            "location": summary[3],
            "license_type": summary[4],
            "status": summary[5],
            "submitted_at": datetime.fromtimestamp(summary[6]),
            "approval_date": datetime.fromtimestamp(summary[7]) if summary[7] else None,
            "expiry_date": datetime.fromtimestamp(summary[8]) if summary[8] else None,
            "is_active": summary[9],
            "seed_details": {
                "seed_variety": summary[10][0],
                "crop_type": summary[10][1],
                "quantity": summary[10][2],
                "quality_parameters": summary[10][3],
                "source": summary[10][4],
            }
        }, status=status.HTTP_200_OK)

    except Exception as exc:
        logger.exception("Unhandled exception in department_licenses_view")
        return ApiResponse(err="Internal server error: " + str(exc), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@authentication_classes([APIKeyAuthentication])
def department_license_status_view(request, id):
    """
    Update the status of a license application

    Parameters:
    - id: License application ID (path parameter)
    - status: New status for the license (required in request body)
    - remarks: Optional remarks about the status change
    - documents_hash: Optional hash of attached documents

    Returns:
    - 200: Success response with updated license details
    - 400: Bad request if status is missing
    - 401: Unauthorized if not authenticated
    - 403: Forbidden if user doesn't have permission
    - 404: License not found
    - 500: Internal server error
    """
    try:
        license_id = id
        docs_hash = request.data.get("docs_hash", b"")
        if not license_id:
            return ApiResponse(err="Missing required query parameter: 'id'", status=status.HTTP_400_BAD_REQUEST)

        try:
            license_id = int(license_id)
        except ValueError:
            return ApiResponse(err="License ID must be a valid integer", status=status.HTTP_400_BAD_REQUEST)
        # Validate request data
        new_status = request.data.get('status')
        remarks = request.data.get('remarks', '')
        if new_status is None or not (0 <= new_status <= 7):
            return ApiResponse(err="Invalid or missing 'status'", status=400)
        if new_status in {5, 6} and not remarks:
            return ApiResponse(err="Remarks required for rejection/revocation", status=400)
        docs_hash_b = docs_hash.encode() if isinstance(docs_hash, str) else docs_hash
        handler = SeedLicenseHandler()
        try:
            receipt = handler.update_license_status(
                int(license_id), new_status,remarks, None, docs_hash_b)
            return ApiResponse(data={
                "id": license_id,
                "status": new_status,
                "blockchain_tx_id": receipt.transactionHash.hex(),
                "updated_at": receipt.blockNumber,
            })
        except Exception as e:
            logger.error(
                f"Error updating license status for ID {id}",
                exc_info=True,
                extra={'user': request.user.id, 'license_id': id}
            )
            return ApiResponse(
                err=f"Failed to update license status: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except ValueError as e:
        logger.warning(
            f"Invalid input for license update",
            exc_info=True,
            extra={'user': request.user.id, 'license_id': id}
        )
        return ApiResponse(
            err=str(e),
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@authentication_classes([APIKeyAuthentication])
def verify_license_documents(request, id):
    """
    Mark documents as verified for a license application

    Parameters:
    - id: License application ID (path parameter)
    - documents: List of document IDs to verify (required in request body)
    - verification_notes: Optional notes about the verification

    Returns:
    - 200: Success response with verification details
    - 400: Bad request if documents are missing or invalid
    - 401: Unauthorized if not authenticated
    - 403: Forbidden if user doesn't have permission
    - 404: License not found
    - 500: Internal server error
    """
    try:
        documents = request.data.get('documents', [])
        verification_notes = request.data.get('verification_notes', '')
        officer_data = request.data.get('officer_address')
        if not documents:
            return ApiResponse(
                err='At least one document ID is required',
                status=status.HTTP_400_BAD_REQUEST
            )

        # Initialize services
        license_handler = SeedLicenseHandler()
        blockchain_service = BlockchainAPIService()
        #When we will get Authentication API from Rajasthan we will get details from that, then we will use this code.

        # # Verify the user is an authorized officer
        # if not request.user.blockchain_wallet:
        #     return ApiResponse(
        #         err='User has no associated blockchain wallet',
        #         status=status.HTTP_403_FORBIDDEN
        #     )

        officer_address =officer_data
        officer_info = blockchain_service.get_officer_role(officer_address)
        print("Officer information: %s", officer_info)
        if not officer_info.get('is_authorized', False):
            return ApiResponse(
                err='User is not an authorized officer',
                status=status.HTTP_403_FORBIDDEN
            )

        # Update license status to DOCUMENTS_VERIFIED (status code 1)
        result = license_handler.update_license_status(
            license_id=int(id),
            new_status=1,  # DOCUMENTS_VERIFIED
            remarks=f"Documents verified: {', '.join(documents)}. {verification_notes}",
            user=request.user
        )

        if not result:
            return ApiResponse(
                err='Failed to update license status',
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update local license status
        license = License.objects.filter(license_id=id).first()
        if license:
            license.status = "DOCUMENTS_VERIFIED"
            license.save()

        logger.info(
            f"Documents verified for license {id}",
            extra={
                'user': request.user.id,
                'license_id': id,
                'documents': documents
            }
        )

        return ApiResponse(
            data={
                'id': id,
                'verified_documents': documents,
                'verified_at': datetime.now().isoformat(),
                'verified_by': officer_address
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Document verification failed: {str(e)}", exc_info=True)
        return ApiResponse(
            err="Document verification failed",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([APIKeyAuthentication])
def record_field_inspection(request, id):
    """
    Record field inspection results for a license application

    Parameters:
    - id: License application ID (path parameter)
    - inspection_data: Field inspection details (required in request body)
    - inspection_notes: Optional notes about the inspection

    Returns:
    - 200: Success response with inspection details
    - 400: Bad request if inspection data is invalid
    - 401: Unauthorized if not authenticated
    - 403: Forbidden if user doesn't have permission
    - 404: License not found
    - 500: Internal server error
    """
    try:
        inspection_data = request.data.get('inspection_data', {})
        inspection_notes = request.data.get('inspection_notes', '')
        officer_data = request.data.get('officer_address')

        if not inspection_data:
            return ApiResponse(
                err='Inspection data is required',
                status=status.HTTP_400_BAD_REQUEST
            )

        # Initialize services
        license_handler = SeedLicenseHandler()
        blockchain_service = BlockchainAPIService()
        #        #When we will get Authentication API from Rajasthan we will get details from that, then we will use this code.

        # # Verify officer authorization
        # if not request.user.blockchain_wallet:
        #     return ApiResponse(
        #         err='User has no associated blockchain wallet',
        #         status=status.HTTP_403_FORBIDDEN
        #     )

        # officer_address = request.user.blockchain_wallet.address
        officer_address =officer_data
        officer_info = blockchain_service.get_officer_role(officer_address)

        if not officer_info.get('is_authorized', False):
            return ApiResponse(
                err='User is not an authorized officer',
                status=status.HTTP_403_FORBIDDEN
            )

        # Prepare remarks combining all inspection data
        remarks = {
            'inspection_data': inspection_data,
            'notes': inspection_notes,
            'inspector': officer_address
        }

        # Update license status to FIELD_INSPECTION_COMPLETED (status code 2)
        result = license_handler.update_license_status(
            license_id=int(id),
            new_status=2,  # FIELD_INSPECTION_COMPLETED
            remarks=json.dumps(remarks),
            user=request.user
        )

        if not result:
            return ApiResponse(
                err='Failed to update license status',
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update local license status
        license = License.objects.filter(license_id=id).first()
        if license:
            license.status = "FIELD_INSPECTION_COMPLETED"
            license.save()

        logger.info(
            f"Field inspection recorded for license {id}",
            extra={
                'user': request.user.id,
                'license_id': id
            }
        )

        return ApiResponse(
            data={
                'id': id,
                'inspection_id': f"INSP-{id}-{datetime.now().timestamp()}",
                'inspection_date': datetime.now().isoformat(),
                'inspected_by': officer_address
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Field inspection recording failed: {str(e)}", exc_info=True)
        return ApiResponse(
            err="Field inspection recording failed",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([APIKeyAuthentication])
def revoke_license(request, id):
    """
    Revoke an issued license with a reason

    Parameters:
    - id: License application ID (path parameter)
    - reason: Reason for revocation (required in request body)
    - additional_notes: Optional additional notes

    Returns:
    - 200: Success response with revocation details
    - 400: Bad request if reason is missing
    - 401: Unauthorized if not authenticated
    - 403: Forbidden if user doesn't have permission
    - 404: License not found
    - 500: Internal server error
    """
    try:
        reason = request.data.get('reason')
        additional_notes = request.data.get('additional_notes', '')
        officer_data = request.data.get('officer_address')

        if not reason:
            return ApiResponse(
                err='Reason is required for revocation',
                status=status.HTTP_400_BAD_REQUEST
            )

        # Initialize services
        license_handler = SeedLicenseHandler()
        blockchain_service = BlockchainAPIService()
        #When we will get Authentication API from Rajasthan we will get details from that, then we will use this code.

        # # Verify officer authorization
        # if not request.user.blockchain_wallet:
        #     return ApiResponse(
        #         err='User has no associated blockchain wallet',
        #         status=status.HTTP_403_FORBIDDEN
        #     )

        officer_address = officer_data
        officer_info = blockchain_service.get_officer_role(officer_address)

        if officer_info.get('role_id', -1) not in [0, 1]:  # Only Agriculture Officer or District Collector can revoke
            return ApiResponse(
                err='User does not have permission to revoke licenses',
                status=status.HTTP_403_FORBIDDEN
            )

        # Combine reason and additional notes
        full_remarks = f"REVOKED - Reason: {reason}"
        if additional_notes:
            full_remarks += f" | Additional Notes: {additional_notes}"

        # Update license status to REVOKED (status code 6)
        result = license_handler.update_license_status(
            license_id=int(id),
            new_status=6,  # REVOKED
            remarks=full_remarks,
            user=request.user
        )

        if not result:
            return ApiResponse(
                err='Failed to revoke license',
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update local license status
        license = License.objects.filter(license_id=id).first()
        if license:
            license.status = "REVOKED"
            license.save()

        logger.warning(
            f"License {id} revoked by user {request.user.id}",
            extra={
                'user': request.user.id,
                'license_id': id,
                'reason': reason
            }
        )

        return ApiResponse(
            data={
                'id': id,
                'status': 'REVOKED',
                'revoked_at': datetime.now().isoformat(),
                'reason': reason,
                'revoked_by': officer_address
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"License revocation failed: {str(e)}", exc_info=True)
        return ApiResponse(
            err="License revocation failed",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

#Inspection related apis

@api_view(['POST'])
@authentication_classes([APIKeyAuthentication])
def inspection_check_in(request):
    """
    Check in for field inspection

    Parameters:
    - license_id: License application ID (required)
    - location: Geo location coordinates (required)
    - device_info: Information about the checking device (optional)

    Returns:
    - 201: Check-in recorded successfully
    - 400: Bad request if required fields are missing
    - 401: Unauthorized if not authenticated
    - 403: Forbidden if user doesn't have permission
    - 404: License not found
    """
    try:
        # Validate required fields
        license_id = request.data.get('license_id')
        location = request.data.get('location')
        officer_data = request.data.get('officer_address')

        if not license_id or not location:
            return ApiResponse(
                err='Both license_id and location are required',
                status=status.HTTP_400_BAD_REQUEST
            )
        #When we will get Authentication API from Rajasthan we will get details from that, then we will use this code.

        # # Verify officer authorization
        # if not request.user.blockchain_wallet:
        #     return ApiResponse(
        #         err='User has no associated blockchain wallet',
        #         status=status.HTTP_403_FORBIDDEN
        #     )

        # Initialize services
        blockchain_service = BlockchainAPIService()
        license_handler = SeedLicenseHandler()

        # Generate unique inspection ID
        inspection_id = f"INSP-{license_id}-{int(timezone.now().timestamp())}"
        officer = RajOfficer.objects.filter(blockchain_address=officer_data).first()
        # Prepare check-in data
        device_info = request.data.get('device_info', {})
        check_in_data = {
            'license_id': license_id,
            'officer_id': officer.id,
            'location': location,
            'timestamp': timezone.now().isoformat(),
            'device_info': device_info
        }

        # Record inspection start on blockchain
        # To-do: I need smart contract for recording all the inspection details on blockchain if it is required as of now

        result = blockchain_service.record_inspection_start(
            license_id=int(license_id),
            inspection_id=inspection_id,
            inspection_data=json.dumps(check_in_data),
            officer_address=officer_data
        )

        if not result:
            return ApiResponse(
                err='Failed to record inspection start',
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(
            "Inspection check-in recorded",
            extra={
                'user': request.user.id,
                'license_id': license_id,
                'inspection_id': inspection_id,
                'tx_hash': result.get('transaction_hash', '')
            }
        )

        return ApiResponse(
            data={
                'inspection_id': inspection_id,
                'license_id': license_id,
                'officer_id': str(request.user.id),
                'check_in_time': datetime.now().isoformat(),
                'blockchain_tx_id': result.get('transaction_hash', '')
            },
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        logger.error("Inspection check-in failed", exc_info=True)
        return ApiResponse(
            err="Inspection check-in failed",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([APIKeyAuthentication])
def upload_inspection_photo(request):
    """
    Upload photo captured during physical verification

    Parameters:
    - inspection_id: Inspection ID (required)
    - photo: Photo file (required)
    - photo_type: Type of photo (required)
    - location: Geo location coordinates (required)
    - caption: Optional caption for the photo

    Returns:
    - 201: Photo uploaded successfully
    - 400: Bad request if required fields are missing
    - 401: Unauthorized if not authenticated
    - 404: Inspection not found
    """
    try:
        # Validate required fields
        inspection_id = request.POST.get('inspection_id')
        photo_type = request.POST.get('photo_type')
        location = request.POST.get('location')
        photo_file = request.FILES.get('photo')
        officer_data = request.data.get('officer_address')

        if not all([inspection_id, photo_type, location, photo_file]):
            return ApiResponse(
                err='inspection_id, photo, photo_type and location are required',
                status=status.HTTP_400_BAD_REQUEST
            )
        #When we will get Authentication API from Rajasthan we will get details from that, then we will use this code.
        # # Verify officer authorization
        # if not request.user.blockchain_wallet:
        #     return ApiResponse(
        #         err='User has no associated blockchain wallet',
        #         status=status.HTTP_403_FORBIDDEN
        #     )

        # Initialize services
        blockchain_service = BlockchainAPIService()

        # Generate photo ID
        photo_id = f"PHOTO-{inspection_id}-{int(timezone.now().timestamp())}"

        # Save photo to storage
        file_path = f"inspections/{inspection_id}/{photo_id}.jpg"
        saved_path = default_storage.save(file_path, photo_file)
        photo_url = default_storage.url(saved_path)

        # Calculate photo hash
        photo_file.seek(0)
        photo_hash = hashlib.sha256(photo_file.read()).hexdigest()

        # Prepare photo metadata
        photo_data = {
            'inspection_id': inspection_id,
            'photo_type': photo_type,
            'location': json.loads(location),
            'timestamp': timezone.now().isoformat(),
            'officer_id': request.user.id,
            'caption': request.POST.get('caption', '')
        }

        # Record photo on blockchain
        result = blockchain_service.record_inspection_photo(
            inspection_id=inspection_id,
            photo_id=photo_id,
            photo_hash=photo_hash,
            photo_data=json.dumps(photo_data),
            officer_address = officer_data,
            # officer_address=request.user.blockchain_wallet.address
        )

        if not result:
            return ApiResponse(
                err='Failed to record inspection photo',
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(
            "Inspection photo uploaded",
            extra={
                'user': request.user.id,
                'inspection_id': inspection_id,
                'photo_id': photo_id,
                'tx_hash': result.get('transaction_hash', '')
            }
        )

        return ApiResponse(
            data={
                'photo_id': photo_id,
                'inspection_id': inspection_id,
                'photo_url': photo_url,
                'photo_hash': photo_hash,
                'blockchain_tx_id': result.get('transaction_hash', '')
            },
            status=status.HTTP_201_CREATED
        )

    except json.JSONDecodeError:
        return ApiResponse(
            err='Invalid location format',
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error("Photo upload failed", exc_info=True)
        return ApiResponse(
            err="Photo upload failed",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([APIKeyAuthentication])
def complete_inspection(request):
    """
    Complete inspection and record results

    Parameters:
    - inspection_id: Inspection ID (required)
    - result: Inspection result (required)
    - remarks: Inspection remarks (required)
    - location: Geo location coordinates
    - checklist: Inspection checklist

    Returns:
    - 200: Inspection completed successfully
    - 400: Bad request if required fields are missing
    - 401: Unauthorized if not authenticated
    - 404: Inspection not found
    """
    try:
        # Validate required fields
        inspection_id = request.data.get('inspection_id')
        result = request.data.get('result')
        remarks = request.data.get('remarks')
        officer_data = request.data.get('officer_address')

        if not all([inspection_id, result, remarks]):
            return ApiResponse(
                err='inspection_id, result and remarks are required',
                status=status.HTTP_400_BAD_REQUEST
            )
        #When we will get Authentication API from Rajasthan we will get details from that, then we will use this code.
        # Verify officer authorization
        # if not request.user.blockchain_wallet:
        #     return ApiResponse(
        #         err='User has no associated blockchain wallet',
        #         status=status.HTTP_403_FORBIDDEN
        #     )

        # Extract license ID from inspection ID
        license_id = inspection_id.split('-')[1]

        # Initialize services
        blockchain_service = BlockchainAPIService()
        license_handler = SeedLicenseHandler()

        # Prepare inspection results
        inspection_data = {
            'result': result,
            'remarks': remarks,
            'location': request.data.get('location'),
            'checklist': request.data.get('checklist', {}),
            'completed_by': request.user.id,
            'completion_time': timezone.now().isoformat()
        }

        # Record completion on blockchain
        result = blockchain_service.complete_inspection(
            license_id=int(license_id),
            inspection_id=inspection_id,
            inspection_result=result,
            inspection_data=json.dumps(inspection_data),
            officer_address=officer_data
            # officer_address=request.user.blockchain_wallet.address
        )

        if not result:
            return ApiResponse(
                err='Failed to complete inspection',
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(
            "Inspection completed",
            extra={
                'user': request.user.id,
                'inspection_id': inspection_id,
                'result': result,
                'tx_hash': result.get('transaction_hash', '')
            }
        )

        return ApiResponse(
            data={
                'inspection_id': inspection_id,
                'license_id': license_id,
                'result': result,
                'completion_time': datetime.now().isoformat(),
                'blockchain_tx_id': result.get('transaction_hash', '')
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error("Inspection completion failed", exc_info=True)
        return ApiResponse(
            err="Inspection completion failed",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

#Analytics views


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
def license_counts_by_status(request):
    """
    Get license counts grouped by status with filters

    Parameters:
    - from_date: Filter by submission date (from)
    - to_date: Filter by submission date (to)
    - district: Filter by district
    - license_type: Filter by license type

    Returns:
    - 200: License counts by status
    - 401: Unauthorized
    - 403: Forbidden
    """
    try:
        # Get filters from query params
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        district = request.query_params.get('district')
        license_type = request.query_params.get('license_type')

        # Build query filters
        filters = Q()
        if from_date:
            from_dt = datetime.strptime(from_date, '%Y-%m-%d').date()
            filters &= Q(submitted_at__date__gte=from_dt)
        if to_date:
            to_dt = datetime.strptime(to_date, '%Y-%m-%d').date()
            filters &= Q(submitted_at__date__lte=to_dt)
        if district:
            filters &= Q(location__icontains=district)
        if license_type:
            filters &= Q(license_type=license_type)

        # Get counts from database
        counts = License.objects.filter(filters).values('status').annotate(
            count=Count('id')
        ).order_by('status')

        total = License.objects.filter(filters).count()

        return ApiResponse(
            data={
                'total': total,
                'counts': list(counts)
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error getting license counts by status: {str(e)}")
        return ApiResponse(
            err="Failed to retrieve license counts",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
def license_counts_by_type(request):
    """
    Get license counts grouped by type with filters

    Parameters:
    - from_date: Filter by submission date (from)
    - to_date: Filter by submission date (to)
    - district: Filter by district
    - status: Filter by status

    Returns:
    - 200: License counts by type
    - 401: Unauthorized
    - 403: Forbidden
    """
    try:
        # Get filters from query params
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        district = request.query_params.get('district')
        status_filter = request.query_params.get('status')

        # Build query filters
        filters = Q()
        if from_date:
            from_dt = datetime.strptime(from_date, '%Y-%m-%d').date()
            filters &= Q(submitted_at__date__gte=from_dt)
        if to_date:
            to_dt = datetime.strptime(to_date, '%Y-%m-%d').date()
            filters &= Q(submitted_at__date__lte=to_dt)
        if district:
            filters &= Q(location__icontains=district)
        if status_filter:
            filters &= Q(status=status_filter)

        # Get counts from database
        counts = License.objects.filter(filters).values('license_type').annotate(
            count=Count('id')
        ).order_by('license_type')

        total = License.objects.filter(filters).count()

        return ApiResponse(
            data={
                'total': total,
                'counts': list(counts)
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error getting license counts by type: {str(e)}")
        return ApiResponse(
            err="Failed to retrieve license type counts",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
def monthly_license_stats(request):
    """
    Get monthly license statistics with filters

    Parameters:
    - year: Filter by year (default: current year)
    - district: Filter by district
    - license_type: Filter by license type
    - status: Filter by status

    Returns:
    - 200: Monthly license statistics
    - 401: Unauthorized
    - 403: Forbidden
    """
    try:
        year = int(request.query_params.get('year', datetime.now().year))
        district = request.query_params.get('district')
        license_type = request.query_params.get('license_type')
        status_filter = request.query_params.get('status')

        # Initialize monthly stats
        monthly_stats = []
        for month in range(1, 13):
            monthly_stats.append({
                'month': month,
                'month_name': calendar.month_name[month],
                'applications': 0,
                'approved': 0,
                'rejected': 0,
                'pending': 0
            })

        # Build base filters for the year
        filters = Q(submitted_at__year=year)
        if district:
            filters &= Q(location__icontains=district)
        if license_type:
            filters &= Q(license_type=license_type)
        if status_filter:
            filters &= Q(status=status_filter)

        # Get all licenses for the year with filters
        licenses = License.objects.filter(filters)

        # Process each license
        for license in licenses:
            month = license.submitted_at.month
            monthly_stats[month - 1]['applications'] += 1

            if license.status == 'APPROVED':
                monthly_stats[month - 1]['approved'] += 1
            elif license.status == 'REJECTED':
                monthly_stats[month - 1]['rejected'] += 1
            elif license.status in ['APPLIED', 'DOCUMENTS_VERIFIED', 'FIELD_INSPECTION_COMPLETED']:
                monthly_stats[month - 1]['pending'] += 1

        total = licenses.count()

        return ApiResponse(
            data={
                'year': year,
                'total': total,
                'monthly_stats': monthly_stats
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error getting monthly stats: {str(e)}")
        return ApiResponse(
            err="Failed to retrieve monthly statistics",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
def licenses_by_district(request):
    """
    Get license statistics grouped by district with filters

    Parameters:
    - from_date: Filter by submission date (from)
    - to_date: Filter by submission date (to)
    - license_type: Filter by license type
    - status: Filter by application status

    Returns:
    - 200: License statistics by district
    - 401: Unauthorized
    - 403: Forbidden
    """
    try:
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        license_type = request.query_params.get('license_type')
        status_filter = request.query_params.get('status')

        # Build query filters
        filters = Q()
        if from_date:
            from_dt = datetime.strptime(from_date, '%Y-%m-%d').date()
            filters &= Q(submitted_at__date__gte=from_dt)
        if to_date:
            to_dt = datetime.strptime(to_date, '%Y-%m-%d').date()
            filters &= Q(submitted_at__date__lte=to_dt)
        if license_type:
            filters &= Q(license_type=license_type)
        if status_filter:
            filters &= Q(status=status_filter)

        # Get all licenses with filters
        licenses = License.objects.filter(filters)

        # Initialize district stats
        district_stats = defaultdict(lambda: {
            'applications': 0,
            'approved': 0,
            'rejected': 0,
            'pending': 0
        })

        # Process each license
        for license in licenses:
            # Extract district from location (simplified)
            location = license.location
            district = location.split(',')[-1].strip() if ',' in location else location

            district_stats[district]['applications'] += 1

            if license.status == 'APPROVED':
                district_stats[district]['approved'] += 1
            elif license.status == 'REJECTED':
                district_stats[district]['rejected'] += 1
            elif license.status in ['APPLIED', 'DOCUMENTS_VERIFIED', 'FIELD_INSPECTION_COMPLETED']:
                district_stats[district]['pending'] += 1

        total = licenses.count()

        # Format response
        stats_list = [{
            'district': district,
            **stats
        } for district, stats in district_stats.items()]

        return ApiResponse(
            data={
                'total': total,
                'district_stats': stats_list
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error getting district stats: {str(e)}")
        return ApiResponse(
            err="Failed to retrieve district statistics",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
def officer_performance_metrics(request):
    """
    Get officer performance metrics with filters

    Parameters:
    - from_date: Filter by date (from)
    - to_date: Filter by date (to)
    - officer_id: Filter by officer ID (address)
    - district: Filter by district

    Returns:
    - 200: Officer performance metrics
    - 401: Unauthorized
    - 403: Forbidden
    """
    try:
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        officer_address = request.query_params.get('officer_id')
        district = request.query_params.get('district')

        # Initialize blockchain services
        blockchain_service = BlockchainAPIService()
        license_handler = SeedLicenseHandler()

        # Get all transactions filtered by officer if specified
        tx_filters = {}
        if officer_address:
            if not Web3.is_address(officer_address):
                return ApiResponse(
                    err="Invalid officer address format",
                    status=status.HTTP_400_BAD_REQUEST
                )
            tx_filters['created_by__address'] = officer_address.lower()

        if from_date:
            from_dt = datetime.strptime(from_date, '%Y-%m-%d').date()
            tx_filters['timestamp__date__gte'] = from_dt
        if to_date:
            to_dt = datetime.strptime(to_date, '%Y-%m-%d').date()
            tx_filters['timestamp__date__lte'] = to_dt

        # Get transactions from database
        transactions = BlockchainTransaction.objects.filter(
            action_type__in=['STATUS_UPDATE', 'LICENSE_APPLY'],
            **tx_filters
        ).select_related('license', 'created_by')

        # Initialize metrics dictionary
        officer_metrics = defaultdict(lambda: {
            'applications_processed': 0,
            'applications_approved': 0,
            'applications_rejected': 0,
            'inspections_conducted': 0,
            'processing_times': []
        })

        # Process each transaction
        for tx in transactions:
            if not tx.created_by:
                continue

            officer_address = tx.created_by.address.lower()
            officer = officer_metrics[officer_address]

            # Apply district filter if specified
            if district and district.lower() not in tx.license.location.lower():
                continue

            # Count actions by type
            if tx.action_type == 'STATUS_UPDATE':
                # Get license status change details
                try:
                    license_summary = license_handler.get_license_summary(tx.license.license_id)
                    new_status = license_summary[9]  # status is at index 9 in the summary

                    if new_status in [4, 5]:  # APPROVED or REJECTED
                        officer['applications_processed'] += 1
                        if new_status == 4:  # APPROVED
                            officer['applications_approved'] += 1
                        else:  # REJECTED
                            officer['applications_rejected'] += 1

                        # Calculate processing time
                        app_date = tx.license.submitted_at
                        action_date = tx.timestamp
                        processing_time = (action_date - app_date).total_seconds() / 3600
                        officer['processing_times'].append(processing_time)

                    elif new_status == 2:  # FIELD_INSPECTION_COMPLETED
                        officer['inspections_conducted'] += 1

                except Exception as e:
                    logger.error(f"Error processing license {tx.license.license_id}: {str(e)}")
                    continue

        # Format response
        metrics_list = []
        for officer_address, metrics in officer_metrics.items():
            # Get officer details
            try:
                officer_info = blockchain_service.get_officer_role(officer_address)
                avg_time = sum(metrics['processing_times']) / len(metrics['processing_times']) if metrics[
                    'processing_times'] else 0

                metrics_list.append({
                    'officer_id': officer_address,
                    'name': f"Officer {officer_address[:6]}",
                    'role': officer_info['role_name'],
                    'district': "Unknown",  # Could be enhanced with additional officer data
                    'applications_processed': metrics['applications_processed'],
                    'applications_approved': metrics['applications_approved'],
                    'applications_rejected': metrics['applications_rejected'],
                    'average_processing_time': round(avg_time, 2),
                    'inspections_conducted': metrics['inspections_conducted']
                })
            except Exception as e:
                logger.error(f"Error getting officer info for {officer_address}: {str(e)}")
                continue

        return ApiResponse(
            data={
                'total_officers': len(metrics_list),
                'officer_metrics': metrics_list
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error getting officer metrics: {str(e)}")
        return ApiResponse(
            err="Failed to retrieve officer performance metrics",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )