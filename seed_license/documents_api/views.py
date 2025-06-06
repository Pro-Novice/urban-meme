import logging
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes, parser_classes
)
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils.timezone import now
from Services.api_response import ApiResponse

from .models import Document
from .utils import sha256_file
# from .document_handler import DocumentHandler
from seed_license.blockchain_api.authentication import APIKeyAuthentication

logger = logging.getLogger(__name__)
# dh = DocumentHandler()

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
@parser_classes([MultiPartParser])
def upload_document_view(request):
    documents = request.FILES.getlist("document")

    if not documents:
        return ApiResponse(
            err="No files uploaded. Please attach one or more documents.",
            status=status.HTTP_400_BAD_REQUEST
        )

    response_data = []

    for document in documents:
        allowed_types = ['application/pdf', 'image/jpeg', 'image/png']
        if document.content_type not in allowed_types:
            return ApiResponse(
                err=f"File type not allowed: {document.content_type}",
                status=status.HTTP_400_BAD_REQUEST
            )

        # Restrict file size (e.g., 5MB)
        max_size_mb = 5
        if document.size > max_size_mb * 1024 * 1024:
            return ApiResponse(
                err=f"File '{document.name}' exceeds size limit of {max_size_mb}MB",
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            sha256 = sha256_file(document)
        except Exception as e:
            logger.exception(f"Error generating SHA256 for file: {document.name}")
            return ApiResponse(err=f"Hashing failed for {document.name}: {str(e)}",
                               status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        document.seek(0)

        try:
            doc = Document.objects.create(
                owner=request.user,
                file=document,
                filename=document.name,
                sha256_hash=sha256
            )
        except Exception as e:
            logger.exception(f"Error saving Document instance for file: {document.name}")
            return ApiResponse(err=f"Database save failed for {document.name}: {str(e)}",
                               status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response_data.append({
            "id": doc.id,
            "owner": str(doc.owner),
            "filename": doc.filename,
            "sha256_hash": doc.sha256_hash,
            "uploaded_at": doc.uploaded_at or now()
        })

    return ApiResponse(data=response_data, status=status.HTTP_201_CREATED)

@api_view(["GET"])
@authentication_classes([APIKeyAuthentication])
# @permission_classes([IsAuthenticated])
def get_document_view(request, id):
    try:
        doc = Document.objects.get(id=id, owner=request.user)
    except Document.DoesNotExist:
        return ApiResponse(err="Document not found.", status=status.HTTP_404_NOT_FOUND)

    return ApiResponse(data={
        "id": doc.id,
        "filename": doc.filename,
        "sha256_hash": doc.sha256_hash,
        # "blockchain_doc_id": doc.blockchain_doc_id,
        # "blockchain_tx_id": doc.blockchain_tx_id,
        "uploaded_at": doc.uploaded_at
    })

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
# @permission_classes([IsAuthenticated])
def verify_document_view(request):
    doc_id = request.data.get("doc_id")
    if not doc_id:
        return ApiResponse(err="Missing required field: doc_id", status=status.HTTP_400_BAD_REQUEST)

    try:
        doc = Document.objects.get(id=doc_id, owner=request.user)
    except Document.DoesNotExist:
        return ApiResponse(err="Document not found", status=status.HTTP_404_NOT_FOUND)

    # try:
    #     is_valid = dh.verify_document(doc.blockchain_doc_id, doc.sha256_hash)
    # except Exception as exc:
    #     logger.exception("Verification failed")
    #     return JsonResponse({
    #         "error": str(exc)
    #     }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return ApiResponse(data={
        "document_id": doc.id,
        # "verified": is_valid,
        "sha256_hash": doc.sha256_hash,
    #     "blockchain_doc_id": doc.blockchain_doc_id,
    #     "blockchain_tx_id": doc.blockchain_tx_id
    })
