# api_views.py
import requests
import json
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from urllib.parse import quote

from rest_framework.decorators import authentication_classes, api_view
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR

from Services.api_response import ApiResponse
from seed_license.blockchain_api.authentication import APIKeyAuthentication
from seed_license.models import DocumentUploadLog


@csrf_exempt
@authentication_classes([APIKeyAuthentication])
@api_view(["POST"])
def add_document_to_evault(request):
    """
    API endpoint to add document to Rajasthan eVault
    Expected POST data:
    {
        "deptKey": "DEPT500",
        "documentType": "Demo Citizen Certificate",
        "base64": "JVBERi0xLjQ...",  // Base64 encoded document
        "DocumentMetadata": {
            "MemberID": "12345678901",
            // ... other metadata fields
        },
        "client_id": "dc9a92d1f42ef055c81cca5383ef48ee"  // Optional, falls back to settings
    }
    """
    try:
        # Parse the incoming JSON data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return ApiResponse(err= 'Invalid JSON data', status=400)

        # Validate required fields
        required_fields = ['deptKey', 'documentType', 'base64', 'DocumentMetadata']
        for field in required_fields:
            if field not in data:
                return ApiResponse(err={
                    'status': 'ERROR',
                    'message': f'Missing required field: {field}'
                }, status=HTTP_400_BAD_REQUEST)

        # Prepare the payload for eVault API (excluding client_id)
        payload = {
            "deptKey": data['deptKey'],
            "documentType": data['documentType'],
            "base64": data['base64'],
            "DocumentMetadata": data['DocumentMetadata']
        }

        # Get client_id from request or fall back to settings
        client_id = request.query_params.get('client_id', None)
        if not client_id:
            return ApiResponse(err={
                'status': 'ERROR',
                'message': 'client_id is required either in request'
            }, status=HTTP_400_BAD_REQUEST)

        # Get the API endpoint from settings
        evault_api_url = getattr(settings, 'EVAULT_API_URL',
                                 'https://apitest.sewadwaar.rajasthan.gov.in/app/live/Rajevault/Staging/webservices/api/')

        # URL encode the document type and construct full URL with client_id as query param
        document_type = 'Demo Citizen'
        api_name='addDocument/'
        full_url = f"{evault_api_url}{api_name}{document_type}?client_id={client_id}"

        # Make the request to eVault API
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.post(full_url, json=payload, headers=headers)
        response_data = response.json()

        # Log the request and response
        metadata = data['DocumentMetadata']
        log_entry = DocumentUploadLog.objects.create(
            dept_key=data['deptKey'],
            document_type=data['documentType'],
            member_id=metadata.get('MemberID'),
            enrollment_id=metadata.get('EnrollmentID'),
            certificate_id=metadata.get('CertificateId'),
            jan_aadhaar_id=metadata.get('JanAadhaarID'),
            aadhaar_ref_no=metadata.get('AadhaarRefNo'),
            full_name=metadata.get('FullName'),
            request_data=payload,
            response_data=response_data,
            evault_doc_id=response_data.get('evaultDocId'),
            status=response_data.get('status', 'ERROR'),
            message=response_data.get('message', 'No message received'),
            incident_id=response_data.get('incidentId'),
            client_id_used=client_id,
            is_update=False
        )
        if response_data['status'] == 'ERROR':
            return ApiResponse(err=response_data['message'], status=response.status_code)
        # Return the response from eVault API
        return ApiResponse(data=response_data,status=HTTP_200_OK)
    except Exception as e:
        return ApiResponse(err={
            'status': 'ERROR',
            'message': str(e)
        }, status=HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@authentication_classes([APIKeyAuthentication])
@api_view(["POST"])
def update_document_in_evault(request):
    """
    API endpoint to update document in Rajasthan eVault
    Expected POST data:
    {
        "deptKey": "DEPT500",
        "documentType": "Demo Citizen Certificate",
        "base64": "JVBERi0xLjQ...",  // Base64 encoded document
        "DocumentMetadata": {
            "MemberID": "12345678901",
            // ... other metadata fields
        },
        "client_id": "dc9a92d1f42ef055c81cca5383ef48ee"  // Optional, falls back to settings
    }
    """
    try:
        # Parse the incoming JSON data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return ApiResponse(err='Invalid JSON data', status=400)

        # Validate required fields
        required_fields = ['deptKey', 'documentType', 'base64', 'DocumentMetadata']
        for field in required_fields:
            if field not in data:
                return ApiResponse(err={
                    'status': 'ERROR',
                    'message': f'Missing required field: {field}'
                }, status=HTTP_400_BAD_REQUEST)

        # # Verify documentType in URL matches the one in payload
        # if document_type != data['documentType']:
        #     return ApiResponse(err={
        #         'status': 'ERROR',
        #         'message': 'Document type in URL does not match payload documentType'
        #     }, status=HTTP_400_BAD_REQUEST)

        # Prepare the payload for eVault API (excluding client_id)
        payload = {
            "deptKey": data['deptKey'],
            "documentType": data['documentType'],
            "base64": data['base64'],
            "DocumentMetadata": data['DocumentMetadata']
        }
        api_name = 'updateDocument/'
        # Get client_id from request or fall back to settings
        client_id = request.query_params.get('client_id', None)
        if not client_id:
            return ApiResponse(err={
                'status': 'ERROR',
                'message': 'client_id is required either in request'
            }, status=HTTP_400_BAD_REQUEST)

        # Get the API endpoint from settings
        evault_api_url = getattr(settings, 'EVAULT_API_URL',
                                'https://apitest.sewadwaar.rajasthan.gov.in/app/live/Rajevault/Staging/webservices/api/')

        # URL encode the document type and construct full URL with client_id as query param
        document_type_encoded = 'Demo Citizen'
        full_url = f"{evault_api_url}{api_name}{document_type_encoded}?client_id={client_id}"

        # Make the request to eVault API
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.post(full_url, json=payload, headers=headers)
        response_data = response.json()

        # Log the request and response to the existing DocumentUploadLog model
        metadata = data['DocumentMetadata']
        log_entry = DocumentUploadLog.objects.create(
            dept_key=data['deptKey'],
            document_type=data['documentType'],
            member_id=metadata.get('MemberID'),
            enrollment_id=metadata.get('EnrollmentID'),
            certificate_id=metadata.get('CertificateId'),
            jan_aadhaar_id=metadata.get('JanAadhaarID'),
            aadhaar_ref_no=metadata.get('AadhaarRefNo'),
            full_name=metadata.get('FullName'),
            request_data=payload,
            response_data=response_data,
            evault_doc_id=response_data.get('evaultDocId'),
            status=response_data.get('status', 'ERROR'),
            message=response_data.get('message', 'No message received'),
            incident_id=response_data.get('incidentId'),
            client_id_used=client_id,
            is_update=True  # Add this field to distinguish between add and update operations
        )

        if response_data.get('status') == 'ERROR':
            return ApiResponse(err=response_data.get('message', 'Unknown error'), status=response.status_code)

        # Return the response from eVault API
        return ApiResponse(data=response_data, status=HTTP_200_OK)
    except Exception as e:
        return ApiResponse(err={
            'status': 'ERROR',
            'message': str(e)
        }, status=HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@authentication_classes([APIKeyAuthentication])
@api_view(["POST"])
def fetch_document_from_evault(request):
    """
    API endpoint to fetch document from Rajasthan eVault
    Expected POST data:
    {
        "deptKey": "DEPT500",
        "evaultDocumentId": "{8FD76924-A0F4-41C5-B8EB-4610F6762BD0-30773F97-0000-C11F-812D-2D0324A1542B}",
        "client_id": "dc9a92d1f42ef055c81cca5383ef48ee"  // Optional, falls back to settings
    }
    """
    try:
        # Parse the incoming JSON data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return ApiResponse(err='Invalid JSON data', status=400)

        # Validate required fields
        required_fields = ['deptKey', 'evaultDocumentId']
        for field in required_fields:
            if field not in data:
                return ApiResponse(err={
                    'status': 'ERROR',
                    'message': f'Missing required field: {field}'
                }, status=HTTP_400_BAD_REQUEST)

        # Prepare the payload for eVault API
        payload = {
            "deptKey": data['deptKey'],
            "evaultDocumentId": data['evaultDocumentId']
        }

        api_name = 'fetchDocument/'

        # Get client_id from request or fall back to settings
        client_id = request.query_params.get('client_id', None)
        if not client_id:
            return ApiResponse(err={
                'status': 'ERROR',
                'message': 'client_id is required either in request'
            }, status=HTTP_400_BAD_REQUEST)

        # Get the API endpoint from settings
        evault_api_url = getattr(settings, 'EVAULT_API_URL',
                                 'https://apitest.sewadwaar.rajasthan.gov.in/app/live/Rajevault/Staging/webservices/api/')

        # URL encode the document type and construct full URL with client_id as query param
        document_type_encoded = 'Demo Citizen'
        full_url = f"{evault_api_url}{api_name}{document_type_encoded}?client_id={client_id}"

        # Make the request to eVault API
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.post(full_url, json=payload, headers=headers)
        response_data = response.json()
        if response_data.get('status') == 'ERROR':
            return ApiResponse(err=response_data.get('message', 'Unknown error'), status=response.status_code)

        # Return the response from eVault API
        return ApiResponse(data=response_data, status=HTTP_200_OK)
    except Exception as e:
        return ApiResponse(err={
            'status': 'ERROR',
            'message': str(e)
        }, status=HTTP_500_INTERNAL_SERVER_ERROR)