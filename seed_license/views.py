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
def license_create_view(request):
    required = ["name", "aadhaar", "location", "license_type", "seed_variety",
                "crop_type", "quantity", "quality_parameters", "source"]
    missing = [f for f in required if f not in request.data]
    if missing:
        return ApiResponse(err=f"Missing required fields: {', '.join(missing)}", status=400)

    try:
        handler = SeedLicenseHandler()
        lid, receipt = handler.apply_for_license(request.data, None)  # Changed to None instead of request.user

        # Get block timestamp using the handler's web3 instance
        try:
            block_info = handler.w3.eth.get_block(receipt.blockNumber)
            block_timestamp = datetime.fromtimestamp(block_info.timestamp)
        except Exception as e:
            logger.warning(f"Could not get block timestamp, using current time: {e}")
            block_timestamp = datetime.now()

        return ApiResponse(data={
            "application_id": lid,
            "submitted_at":   block_timestamp.isoformat(),
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
def license_detail_view(request, license_id):
    try:
        summary = SeedLicenseHandler().get_license_summary(int(license_id))
        return ApiResponse(data=summary)
    except Exception as exc:
        logger.exception("License detail fetch error")
        return ApiResponse(err=str(exc), status=500)

# ── POST /api/licenses/{id}/update-status ────────────────────────────
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
def license_status_view(request, license_id):
    # Handle DRF Request vs Django HttpRequest
    if hasattr(request, '_request'):
        django_request = request._request
    else:
        django_request = request
    try:
        print(f"=== Checking license ID: {license_id} ===")
        h = SeedLicenseHandler()
        
        # Make sure we're calling view functions correctly
        try:
            print("Calling getLicenseSummary as view function...")
            
            # Call the contract function directly with .call() for view functions
            contract_function = h.contract.functions.getLicenseSummary(license_id)
            license_summary = contract_function.call()
            
            print(f"License summary result: {license_summary} (type: {type(license_summary)})")
            
            # Extract data from the LicenseSummary struct
            if isinstance(license_summary, (list, tuple)) and len(license_summary) >= 10:
                license_id_from_chain = license_summary[0]
                farmer_address = license_summary[1]
                farmer_name = license_summary[2]
                location = license_summary[3]
                license_type = license_summary[4]  # This is enum value (0,1,2,3,4)
                status = license_summary[5]        # This is enum value (0,1,2,3,4,5,6,7)
                application_date = license_summary[6]
                approval_date = license_summary[7]
                expiry_date = license_summary[8]
                is_active = license_summary[9]
                seed_details = license_summary[10]  # This is a tuple of seed details
                
                # Map status enum to readable string
                status_mapping = {
                    0: "APPLIED",
                    1: "DOCUMENTS_VERIFIED", 
                    2: "FIELD_INSPECTION_COMPLETED",
                    3: "QUALITY_VERIFIED",
                    4: "APPROVED",
                    5: "REJECTED",
                    6: "REVOKED",
                    7: "EXPIRED"
                }
                
                # Map license type enum to readable string
                license_type_mapping = {
                    0: "SEED_PRODUCTION",
                    1: "SEED_DISTRIBUTION",
                    2: "SEED_CERTIFICATION", 
                    3: "HYBRID_SEED_PRODUCTION",
                    4: "ORGANIC_SEED_PRODUCTION"
                }
                
                status_str = status_mapping.get(status, f"UNKNOWN({status})")
                license_type_str = license_type_mapping.get(license_type, f"UNKNOWN({license_type})")
                
                print(f"Extracted status: {status_str} (enum: {status})")
                
            else:
                print(f"Unexpected license summary format: {license_summary}")
                return ApiResponse(err="Invalid license summary format from blockchain", status=500)
                
        except Exception as e:
            print(f"Error in getLicenseSummary: {e}")
            import traceback
            traceback.print_exc()
            return ApiResponse(err=f"Failed to get license details: {str(e)}", status=500)
        
        # Check if license is valid using isLicenseValid function
        try:
            print("Calling isLicenseValid as view function...")
            
            # Call isLicenseValid directly
            is_valid_function = h.contract.functions.isLicenseValid(license_id)
            is_valid = is_valid_function.call()
            
            print(f"Valid result: {is_valid} (type: {type(is_valid)})")
            blockchain_verified = bool(is_valid)
            
        except Exception as e:
            print(f"Error in isLicenseValid: {e}")
            blockchain_verified = False
        
        # Prepare response data
        response_data = {
            "id": license_id,
            "status": status_str,
            "blockchain_verified": blockchain_verified,
            "details": {
                "farmer_name": farmer_name,
                "farmer_address": farmer_address,
                "location": location,
                "license_type": license_type_str,
                "application_date": application_date,
                "approval_date": approval_date if approval_date > 0 else None,
                "expiry_date": expiry_date if expiry_date > 0 else None,
                "is_active": is_active,
            }
        }
        
        # Add seed details if available
        if isinstance(seed_details, (list, tuple)) and len(seed_details) >= 5:
            response_data["details"]["seed_details"] = {
                "seed_variety": seed_details[0],
                "crop_type": seed_details[1], 
                "quantity": seed_details[2],
                "quality_parameters": seed_details[3],
                "source": seed_details[4]
            }
        
        return ApiResponse(data=response_data)
        
    except Exception as exc:
        print(f"Overall error: {exc}")
        import traceback
        traceback.print_exc()
        return ApiResponse(err=str(exc), status=500)




    
# ── GET /api/licenses/{id}/history ───────────────────────────────────
@api_view(["GET"])
def license_history_view(request, license_id):
    try:
        history = SeedLicenseHandler().get_license_history(int(license_id))
        return ApiResponse(data={"id": license_id, "history": history})
    except Exception as exc:
        return ApiResponse(err=str(exc), status=500)

# ── GET /api/licenses/{id}/certificate ───────────────────────────────
@api_view(["GET"])
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

# ── GET /api/licenses (list) ──────────────────────────────────
@api_view(["GET"])
def license_list_view(request):
    # Get all licenses instead of filtering by user
    qs = License.objects.all().order_by("-submitted_at")

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
def transaction_status_view(request, tx_hash):
    info = SeedLicenseHandler().get_transaction_info(tx_hash)
    return ApiResponse(data=info)

# ── GET /api/blockchain/transactions/history ────────────────────────
@api_view(["GET"])
def transaction_history_view(request):
    # Get all transactions instead of filtering by user
    qs = BlockchainTransaction.objects.all().order_by("-timestamp")
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