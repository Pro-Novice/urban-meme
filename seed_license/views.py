import logging
from datetime import datetime
from web3 import Web3
from django.conf import settings
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from Services.api_response import ApiResponse
from Services.exceptions import BlockchainError

from .models import License, BlockchainTransaction
from .permissions import (
    IsFarmer, IsAdmin, IsAgricultureOfficer, IsDistrictCollector,
    IsSeedCertificationOfficer, IsSubsidyApprovalOfficer, IsQualityControlOfficer,
)
from .seed_license_handler import SeedLicenseHandler

logger = logging.getLogger(__name__)

# ── POST /api/licenses/apply ─────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsFarmer])
def license_create_view(request):
    required = ["name", "aadhaar", "location", "license_type", "seed_variety",
                "crop_type", "quantity", "quality_parameters", "source"]
    missing = [f for f in required if f not in request.data]
    if missing:
        return ApiResponse(err=f"Missing required fields: {', '.join(missing)}", status=400)

    try:
        handler = SeedLicenseHandler()
        lid, receipt = handler.apply_for_license(request.data, request.user)

        block_time = Web3().eth.get_block(receipt.blockNumber).timestamp
        return ApiResponse(data={
            "application_id": lid,
            "submitted_at":   datetime.fromtimestamp(block_time).isoformat(),
            "status":         "APPLIED",
            "blockchain_tx_id": receipt.transactionHash.hex(),
        }, status=201)
    except BlockchainError as exc:
        return ApiResponse(err=str(exc), status=400)
    except Exception as exc:
        logger.exception("License application error")
        return ApiResponse(err="Internal server error", status=500)

# ── GET /api/licenses/{id} ───────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def license_detail_view(request, license_id):
    try:
        summary = SeedLicenseHandler().get_license_summary(int(license_id))
        return ApiResponse(data=summary)
    except Exception as exc:
        logger.exception("License detail fetch error")
        return ApiResponse(err=str(exc), status=500)

# ── POST /api/licenses/{id}/update-status ────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def license_status_update_view(request, license_id):
    user = request.user
    if not any([
        user.is_agriculture_officer, user.is_district_collector, user.is_seed_certification_officer,
        user.is_subsidy_approval_officer, user.is_quality_control_officer, user.is_admin,
    ]):
        return ApiResponse(err="Unauthorized", status=403)

    new_status = request.data.get("status")
    if new_status is None or not (0 <= new_status <= 7):
        return ApiResponse(err="Invalid or missing 'status'", status=400)

    if new_status in {5, 6} and not request.data.get("remarks"):
        return ApiResponse(err="Remarks required for rejection/revocation", status=400)

    docs_hash = request.data.get("docs_hash", b"")
    docs_hash_b = docs_hash.encode() if isinstance(docs_hash, str) else docs_hash

    try:
        receipt = SeedLicenseHandler().update_license_status(
            int(license_id), new_status, request.data.get("remarks", ""), user, docs_hash_b)
        return ApiResponse(data={
            "id": license_id,
            "status": new_status,
            "blockchain_tx_id": receipt.transactionHash.hex(),
            "updated_at": receipt.blockNumber,
        })
    except Exception as exc:
        logger.exception("Status update error")
        return ApiResponse(err=str(exc), status=500)

# ── GET /api/licenses/{id}/status ────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def license_status_view(request, license_id):
    try:
        h = SeedLicenseHandler()
        return ApiResponse(data={
            "id": license_id,
            "status": h.get_license_status(int(license_id)),
            "blockchain_verified": h.is_license_valid(int(license_id)),
        })
    except Exception as exc:
        return ApiResponse(err=str(exc), status=500)

# ── GET /api/licenses/{id}/history ───────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def license_history_view(request, license_id):
    try:
        history = SeedLicenseHandler().get_license_history(int(license_id))
        return ApiResponse(data={"id": license_id, "history": history})
    except Exception as exc:
        return ApiResponse(err=str(exc), status=500)

# ── GET /api/licenses/{id}/certificate ───────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def license_certificate_download_view(request, license_id):
    try:
        lic = License.objects.get(license_id=license_id)
    except License.DoesNotExist:
        return ApiResponse(err="License not found", status=404)

    if lic.status != "APPROVED":
        return ApiResponse(err="Certificate not available", status=403)

    summary = SeedLicenseHandler().get_license_summary(int(license_id))
    if summary.get("status") != 4:      # 4 == APPROVED in enum
        return ApiResponse(err="Blockchain status not APPROVED", status=403)

    handler = SeedLicenseHandler()
    return ApiResponse(data={
        "certificate_url": handler.get_certificate_url(license_id),
        "qr_code_url": f"https://rajkisan.rajasthan.gov.in/qrcodes/{license_id}.png",
    })

# ── GET /api/licenses (farmer list) ──────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsFarmer])
def license_list_view(request):
    qs = License.objects.filter(applicant=request.user).order_by("-submitted_at")

    if t := request.query_params.get("type"):
        qs = qs.filter(license_type=t)
    if s := request.query_params.get("status"):
        qs = qs.filter(status=s)

    paginator = PageNumberPagination(); paginator.page_size = 10
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response({
        "total": qs.count(),
        "licenses": [{
            "license_id":   lic.license_id,
            "type":         lic.license_type,
            "status":       lic.status,
            "submitted_at": lic.submitted_at,
            "updated_at":   lic.updated_at,
            "blockchain_tx_id": lic.blockchain_tx_id,
        } for lic in page]
    })

# ── GET /api/blockchain/transactions/{hash} ─────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transaction_status_view(request, tx_hash):
    info = SeedLicenseHandler().get_transaction_info(tx_hash)
    return ApiResponse(data=info)

# ── GET /api/blockchain/transactions/history ────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transaction_history_view(request):
    qs = BlockchainTransaction.objects.filter(created_by=request.user).order_by("-timestamp")
    paginator = PageNumberPagination(); paginator.page_size = 10
    page = paginator.paginate_queryset(qs, request)

    return paginator.get_paginated_response({
        "total": qs.count(),
        "transactions": [{
            "tx_hash":     tx.tx_hash,
            "license_id":  tx.license.license_id,
            "action_type": tx.action_type,
            "status":      tx.status,
            "block_number":tx.block_number,
            "timestamp":   tx.timestamp,
        } for tx in page]
    })