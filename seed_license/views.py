from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from web3 import Web3
import os
import django
from django.conf import settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agri_backend.settings')
django.setup()
from .models import License, BlockchainTransaction
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .seed_license_handler import SeedLicenseHandler
from .permissions import (
    IsFarmer, IsAdmin,
    IsAgricultureOfficer, IsDistrictCollector,
    IsSeedCertificationOfficer, IsSubsidyApprovalOfficer,
    IsQualityControlOfficer
)
from Services.exceptions import BlockchainError
import logging

logger = logging.getLogger(__name__)

class LicenseCreateView(APIView):
    permission_classes = [IsAuthenticated, IsFarmer]

    def post(self, request):
        try:
            data = request.data
            required_fields = [
                'name', 'aadhaar', 'location', 'license_type',
                'seed_variety', 'crop_type', 'quantity', 'quality_parameters', 'source'
            ]
            if not all(field in data for field in required_fields):
                return Response({"error": "Missing required fields"}, status=400)

            handler = SeedLicenseHandler()
            license_id, receipt = handler.apply_for_license(
                data,
                request.user.blockchain_address,
                request.user.private_key,
                request.user
            )

            license_id = receipt.logs[0].args.licenseId if receipt.logs else None
            return Response({
                "license_id": license_id,
                "submitted_at": receipt.blockNumber,
                "status": "APPLIED",
                "blockchain_tx_id": receipt.transactionHash.hex()
            }, status=201)

        except BlockchainError as e:
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            logger.error(f"License application error: {str(e)}")
            return Response({"error": "Internal server error"}, status=500)


class LicenseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, license_id):
        try:
            handler = SeedLicenseHandler()
            summary = handler.get_license_summary(int(license_id))
            return Response(summary)
        except Exception as e:
            logger.error(f"License detail fetch error: {str(e)}")
            return Response({"error": str(e)}, status=500)


class LicenseStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, license_id):
        try:
            if not any([
                request.user.is_agriculture_officer,
                request.user.is_district_collector,
                request.user.is_seed_certification_officer,
                request.user.is_subsidy_approval_officer,
                request.user.is_quality_control_officer,
                request.user.is_admin
            ]):
                return Response({"error": "Unauthorized"}, status=403)

            data = request.data
            if 'status' not in data:
                return Response({"error": "Missing status"}, status=400)

            handler = SeedLicenseHandler()
            receipt = handler.update_license_status(
                license_id,
                data['status'],
                data.get('remarks', ''),
                request.user.blockchain_address,
                request.user.private_key,
                request.user,
                data.get('docs_hash', b'')
            )

            return Response({
                "id": license_id,
                "status": data['status'],
                "blockchain_tx_id": receipt.transactionHash.hex(),
                "updated_at": receipt.blockNumber
            })
        except Exception as e:
            logger.error(f"Status update error: {str(e)}")
            return Response({"error": str(e)}, status=500)


class LicenseStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, license_id):
        try:
            handler = SeedLicenseHandler()
            status = handler.get_license_status(int(license_id))
            valid = handler.is_license_valid(int(license_id))
            return Response({
                "id": license_id,
                "status": status,
                "blockchain_verified": valid
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class LicenseHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, license_id):
        try:
            handler = SeedLicenseHandler()
            history = handler.get_license_history(int(license_id))
            return Response({"id": license_id, "history": history})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class LicenseCertificateDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, license_id):
        try:
            handler = SeedLicenseHandler()
            return Response({
                "certificate_url": handler.get_certificate_url(license_id),
                "qr_code_url": f"https://rajkisan.rajasthan.gov.in/qrcodes/{license_id}.png"
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)



class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'
    max_page_size = 100

class LicenseListView(APIView):
    permission_classes = [IsAuthenticated, IsFarmer]
    pagination_class = StandardResultsSetPagination()

    def get(self, request):
        user = request.user
        queryset = License.objects.filter(applicant=user).order_by("-submitted_at")

        # Filters
        license_type = request.query_params.get('type')
        status = request.query_params.get('status')

        if license_type:
            queryset = queryset.filter(license_type=license_type)
        if status:
            queryset = queryset.filter(status=status)

        paginator = self.pagination_class
        page = paginator.paginate_queryset(queryset, request)
        results = [
            {
                "license_id": lic.license_id,
                "type": lic.license_type,
                "status": lic.status,
                "submitted_at": lic.submitted_at,
                "updated_at": lic.updated_at,
                "blockchain_tx_id": lic.blockchain_tx_id
            } for lic in page
        ]

        return paginator.get_paginated_response({
            "total": queryset.count(),
            "page": request.query_params.get("page", 1),
            "limit": request.query_params.get("limit", 10),
            "licenses": results
        })
    

# class TransactionHistoryView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         queryset = BlockchainTransaction.objects.filter(created_by=request.user).order_by("-timestamp")

#         license_id = request.query_params.get('license_id')
#         tx_type = request.query_params.get('transaction_type')

#         if license_id:
#             queryset = queryset.filter(license__license_id=license_id)
#         if tx_type:
#             queryset = queryset.filter(action_type__iexact=tx_type)

#         paginator = StandardResultsSetPagination()
#         page = paginator.paginate_queryset(queryset, request)
#         results = [
#             {
#                 "tx_hash": tx.tx_hash,
#                 "license_id": tx.license.license_id,
#                 "status": tx.status,
#                 "block_number": tx.block_number,
#                 "timestamp": tx.timestamp,
#                 "action_type": tx.action_type
#             } for tx in page
#         ]

#         return paginator.get_paginated_response({
#             "total": queryset.count(),
#             "page": request.query_params.get("page", 1),
#             "limit": request.query_params.get("limit", 10),
#             "transactions": results
#         })

# class TransactionStatusView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, tx_hash):
#         try:
#             w3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_URL))
#             receipt = w3.eth.get_transaction_receipt(tx_hash)
#             confirmations = w3.eth.block_number - receipt.blockNumber
#             block = w3.eth.get_block(receipt.blockNumber)
#             return Response({
#                 "tx_hash": tx_hash,
#                 "status": "CONFIRMED" if receipt.status == 1 else "FAILED",
#                 "block_number": receipt.blockNumber,
#                 "timestamp": block.timestamp,
#                 "confirmations": confirmations
#             })
#         except Exception as e:
#             return Response({"error": str(e)}, status=404)