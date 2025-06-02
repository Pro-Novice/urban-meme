import logging
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes, parser_classes
)
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils.timezone import now
from django.http import JsonResponse

from .models import Document
from .utils import sha256_file
from .document_handler import DocumentHandler
from blockchain_api.authentication import APIKeyAuthentication

logger = logging.getLogger(__name__)
dh = DocumentHandler()

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def upload_document_view(request):
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({
            "error": "File part 'file' is missing."
        }, status=status.HTTP_400_BAD_REQUEST)

    sha256 = sha256_file(f)
    try:
        doc_id, receipt = dh.store_document_hash(sha256)
    except Exception as exc:
        logger.exception("Blockchain store failed")
        return JsonResponse({
            "error": f"Blockchain error: {str(exc)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    doc = Document.objects.create(
        owner=request.user,
        file=f,
        filename=f.name,
        sha256_hash=sha256,
        blockchain_doc_id=doc_id,
        blockchain_tx_id=receipt.transactionHash.hex(),
    )

    return JsonResponse({
        "id": doc.id,
        "filename": doc.filename,
        "sha256_hash": sha256,
        "blockchain_doc_id": doc.blockchain_doc_id,
        "blockchain_tx_id": doc.blockchain_tx_id,
        "uploaded_at": now()
    }, status=status.HTTP_201_CREATED)

@api_view(["GET"])
@authentication_classes([APIKeyAuthentication])
@permission_classes([IsAuthenticated])
def get_document_view(request, id):
    try:
        doc = Document.objects.get(id=id, owner=request.user)
    except Document.DoesNotExist:
        return JsonResponse({
            "error": "Document not found."
        }, status=status.HTTP_404_NOT_FOUND)

    return JsonResponse({
        "id": doc.id,
        "filename": doc.filename,
        "sha256_hash": doc.sha256_hash,
        "blockchain_doc_id": doc.blockchain_doc_id,
        "blockchain_tx_id": doc.blockchain_tx_id,
        "uploaded_at": doc.uploaded_at
    })

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
@permission_classes([IsAuthenticated])
def verify_document_view(request):
    doc_id = request.data.get("doc_id")
    if not doc_id:
        return JsonResponse({
            "error": "Missing required field: doc_id"
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        doc = Document.objects.get(id=doc_id, owner=request.user)
    except Document.DoesNotExist:
        return JsonResponse({
            "error": "Document not found"
        }, status=status.HTTP_404_NOT_FOUND)

    try:
        is_valid = dh.verify_document(doc.blockchain_doc_id, doc.sha256_hash)
    except Exception as exc:
        logger.exception("Verification failed")
        return JsonResponse({
            "error": str(exc)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return JsonResponse({
        "document_id": doc.id,
        "verified": is_valid,
        "sha256_hash": doc.sha256_hash,
        "blockchain_doc_id": doc.blockchain_doc_id,
        "blockchain_tx_id": doc.blockchain_tx_id
    })
