import logging
from rest_framework.decorators import (
    api_view, authentication_classes, parser_classes
)
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from django.utils.timezone import now
from Services.api_response import ApiResponse
from .utils import sha256_file
from seed_license.blockchain_api.authentication import RajSSOAuthentication
logger = logging.getLogger(__name__)


@api_view(["POST"])
@authentication_classes([RajSSOAuthentication])
@parser_classes([MultiPartParser])
def upload_document_view(request):
    pdf_file = request.FILES.get("document")

    if not pdf_file:
        return ApiResponse(
            err="Missing document pdf in request.",
            status=status.HTTP_400_BAD_REQUEST
        )

    if pdf_file.content_type != 'application/pdf':
        return ApiResponse(
            err=f"Invalid file type: {pdf_file.content_type}. Only PDF allowed.",
            status=status.HTTP_400_BAD_REQUEST
        )

    max_size_mb = 5
    if pdf_file.size > max_size_mb * 1024 * 1024:
        return ApiResponse(
            err=f"File exceeds maximum size of {max_size_mb}MB.",
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        sha256 = sha256_file(pdf_file)
    except Exception as e:
        logger.exception(f"Hash generation failed for {pdf_file.name}")
        return ApiResponse(
            err=f"Hash generation failed: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return ApiResponse(
        data={
            "filename": pdf_file.name,
            "sha256_hash": sha256,
            "generated_at": now()
        },
        status=status.HTTP_200_OK
    )


@api_view(["POST"])
@authentication_classes([RajSSOAuthentication])
@parser_classes([MultiPartParser])
def compare_pdf_hashes(request):
    file1 = request.FILES.get("document1")
    file2 = request.FILES.get("document2")

    if not file1 or not file2:
        return ApiResponse(
            err="Both 'document1' and 'document2' must be provided.",
            status=status.HTTP_400_BAD_REQUEST
        )

    for f in [file1, file2]:
        if f.content_type != 'application/pdf':
            return ApiResponse(
                err=f"Invalid file type: {f.content_type}. Only PDFs are allowed.",
                status=status.HTTP_400_BAD_REQUEST
            )

        max_size_mb = 5
        if f.size > max_size_mb * 1024 * 1024:
            return ApiResponse(
                err=f"File '{f.name}' exceeds max size of {max_size_mb}MB.",
                status=status.HTTP_400_BAD_REQUEST
            )

    try:
        hash1 = sha256_file(file1)
        hash2 = sha256_file(file2)
    except Exception as e:
        logger.exception("Error generating hashes")
        return ApiResponse(
            err=f"Hashing failed: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return ApiResponse(data={
        "filename1": file1.name,
        "filename2": file2.name,
        "sha256_hash1": hash1,
        "sha256_hash2": hash2,
        "are_equal": hash1 == hash2,
        "generated_at": now()
    }, status=status.HTTP_200_OK)

