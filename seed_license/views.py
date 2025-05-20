import logging
from datetime import datetime
from django.utils.timezone import make_aware
from web3 import Web3
from django.conf import settings
from django.db.models import Q
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from .blockchain_api.authentication import APIKeyAuthentication
from Services.api_response import ApiResponse
from Services.exceptions import BlockchainError

from .models import License, BlockchainTransaction, OfficerAction
from .permissions import (
    IsFarmer, IsAdmin, IsAgricultureOfficer, IsDistrictCollector,
    IsSeedCertificationOfficer, IsSubsidyApprovalOfficer, IsQualityControlOfficer,
)
from .seed_license_handler import SeedLicenseHandler
from .blockchain_services import w3
logger = logging.getLogger(__name__)


@api_view(["POST"])
def license_create_view(request):
    try:
        required_fields = ["name", "aadhaar", "location", "license_type", 
                           "seed_variety", "crop_type", "quantity", 
                           "quality_parameters", "source"]
        
        if missing := [f for f in required_fields if f not in request.data]:
            return ApiResponse(
                err=f"Missing required fields: {', '.join(missing)}", 
                status=400
            )

        handler = SeedLicenseHandler()
        lid, receipt = handler.apply_for_license(request.data, None)

        block = w3.eth.get_block(receipt.blockNumber)
        return ApiResponse(data={
            "license_id": lid,
            "submitted_at": make_aware(datetime.fromtimestamp(block.timestamp)),
            "status": "APPLIED",
            "blockchain_tx_id": receipt.transactionHash.hex(),
        }, status=201)
        
    except BlockchainError as exc:
        logger.error("Blockchain error: %s", str(exc))
        return ApiResponse(err=str(exc), status=400)
    except Exception as exc:
        logger.exception("License application failed")
        return ApiResponse(err="Internal server error", status=500)


@api_view(["GET"])
def license_detail_view(request, license_id):
    try:
        summary = SeedLicenseHandler().get_license_summary(int(license_id))

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
        })
    except Exception as exc:
        logger.exception("License detail fetch error")
        return ApiResponse(err=str(exc), status=500)

@api_view(["POST"])
def license_status_update_view(request, license_id):
    new_status = request.data.get("status")
    if new_status is None or not (0 <= new_status <= 7):
        return ApiResponse(err="Invalid or missing 'status'", status=400)

    if new_status in {5, 6} and not request.data.get("remarks"):
        return ApiResponse(err="Remarks required for rejection/revocation", status=400)

    docs_hash = request.data.get("docs_hash", b"")
    docs_hash_b = docs_hash.encode() if isinstance(docs_hash, str) else docs_hash

    try:
        receipt = SeedLicenseHandler().update_license_status(
            int(license_id), new_status, request.data.get("remarks", ""), None, docs_hash_b)
        block = w3.eth.get_block(receipt.blockNumber)
        return ApiResponse(data={
            "license_id": int(license_id),
            "status": new_status,
            "updated_at": make_aware(datetime.fromtimestamp(block.timestamp)),
            "blockchain_tx_id": receipt.transactionHash.hex(),
        })
    except Exception as exc:
        logger.exception("Status update error")
        return ApiResponse(err=str(exc), status=500)


@api_view(["GET"])
def license_status_view(request, license_id):
    try:
        h = SeedLicenseHandler()
        return ApiResponse(data={
            "license_id": int(license_id),
            "status": h.get_license_status(int(license_id)),
            "blockchain_verified": h.is_license_valid(int(license_id)),
        })
    except Exception as exc:
        return ApiResponse(err=str(exc), status=500)


@api_view(["GET"])
def license_history_view(request, license_id):
    try:
        history = SeedLicenseHandler().get_license_history(int(license_id))
        return ApiResponse(data={
            "license_id": int(license_id),
            "history": history
        })
    except Exception as exc:
        return ApiResponse(err=str(exc), status=500)

@api_view(["GET"])
def license_certificate_download_view(request, license_id):
    try:
        lic = License.objects.get(license_id=license_id)
    except License.DoesNotExist:
        return ApiResponse(err="License not found", status=404)

    if lic.status != "APPROVED":
        return ApiResponse(err="Certificate not available", status=403)

    summary = SeedLicenseHandler().get_license_summary(int(license_id))
    if summary[5] != 4: 
        return ApiResponse(err="Blockchain status not APPROVED", status=403)

    handler = SeedLicenseHandler()
    return ApiResponse(data={
        "certificate_url": handler.get_certificate_url(license_id),
        "qr_code_url": f"https://rajkisan.rajasthan.gov.in/qrcodes/{license_id}.png",
    })


@api_view(["GET"])
def license_list_view(request):
    qs = License.objects.all().order_by("-submitted_at")

    if t := request.query_params.get("type"):
        qs = qs.filter(license_type=t)
    if s := request.query_params.get("status"):
        qs = qs.filter(status=s)
    # if request.user.role == 'FARMER':
    #    qs = qs.filter(applicant=request.user)
    paginator = PageNumberPagination()
    paginator.page_size = 10
    page = paginator.paginate_queryset(qs, request)

    return paginator.get_paginated_response({
        "total": qs.count(),
        "licenses": [{
            "license_id": lic.license_id,
            "license_type": lic.license_type,
            "status": lic.status,
            "submitted_at": lic.submitted_at,
            "updated_at": lic.updated_at,
            "blockchain_tx_id": lic.blockchain_tx_id,
        } for lic in page]
    })


@api_view(["GET"])
@authentication_classes([APIKeyAuthentication])
def transaction_status_view(request, tx_hash):
    info = SeedLicenseHandler().get_transaction_info(tx_hash)
    return ApiResponse(data=info)

@api_view(["GET"])
@authentication_classes([APIKeyAuthentication])
def transaction_history_view(request):
    qs = BlockchainTransaction.objects.all().order_by("-timestamp")
    paginator = PageNumberPagination()
    paginator.page_size = 10
    page = paginator.paginate_queryset(qs, request)

    return paginator.get_paginated_response({
        "total": qs.count(),
        "transactions": [{
            "tx_hash": tx.tx_hash,
            "license_id": tx.license.license_id,
            "action_type": tx.action_type,
            "status": tx.status,
            "block_number": tx.block_number,
            "timestamp": tx.timestamp,
        } for tx in page]
    })


@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
def record_officer_action_view(request):
    required_fields = ["license_id", "action_type", "remarks", "tx_hash"]
    if missing := [f for f in required_fields if f not in request.data]:
        return ApiResponse(err=f"Missing required fields: {', '.join(missing)}", status=400)

    try:
        license_id = request.data["license_id"]
        lic = License.objects.get(license_id=license_id)

      
        _, officer_id = request.successful_authenticator.authenticate(request)
        if not officer_id:
            return ApiResponse(err="Officer ID not identified from API key", status=401)

        OfficerAction.objects.create(
            officer_id=str(officer_id),
            license=lic,
            action_type=request.data["action_type"],
            remarks=request.data["remarks"],
            tx_hash=request.data["tx_hash"]
        )
    
        return ApiResponse(data={"message": "Officer action recorded successfully."}, status=201)

    except License.DoesNotExist:
        return ApiResponse(err="License not found", status=404)
    except Exception as exc:
        return ApiResponse(err=str(exc), status=500)

@api_view(["GET"])
@authentication_classes([APIKeyAuthentication])
def get_officer_actions_view(request, officer_id):
    try:
        actions = OfficerAction.objects.filter(officer_id=officer_id).order_by("-timestamp")
        data = [{
            "license_id": action.license.license_id,
            "action_type": action.action_type,
            "remarks": action.remarks,
            "tx_hash": action.tx_hash,
            "timestamp": action.timestamp,
        } for action in actions]
        return ApiResponse(data={"officer_id": officer_id, "actions": data})
    except Exception as exc:
        return ApiResponse(err=str(exc), status=500)
