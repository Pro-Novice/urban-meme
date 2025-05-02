"""Views for handling Raj Kisan Officer registration, listing, detail, update, and deletion."""

from datetime import datetime
from django.forms.models import model_to_dict
from rest_framework.decorators import api_view
from rest_framework import status
from Services.api_response import ApiResponse
from Services.logger import logger
from Raj_Officer.models import RajOfficer
from Raj_Officer.serializer import RajasthanOfficerSerializer


@api_view(['POST'])
def register_raj_kisan_officer(request):
    """Registers a new Raj Kisan officer."""
    logger.info("Data to be registered: %s", request.data)
    serializer = RajasthanOfficerSerializer(data=request.data)

    if serializer.is_valid():
        try:
            officer = serializer.save()
            logger.info("Officer registered successfully: %s", model_to_dict(officer))
            return ApiResponse(data=serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("Error saving officer")
            return ApiResponse(err=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return ApiResponse(err=serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def list_all_raj_kisan_officers(request):
    """Returns a list of all Raj Kisan officers."""
    try:
        officers = RajOfficer.objects.all()
        serializer = RajasthanOfficerSerializer(officers, many=True)
        return ApiResponse(data=serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.exception("Error fetching officers list")
        return ApiResponse(err=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_raj_kisan_officer_detail(request):
    """Returns details of a specific officer based on user ID."""
    officer_id = request.query_params.get('id')
    if not officer_id:
        return ApiResponse(err="Missing officer ID in query parameters",
                           status=status.HTTP_400_BAD_REQUEST)

    try:
        officer = RajOfficer.objects.get(user_id=officer_id)
        serializer = RajasthanOfficerSerializer(officer)
        return ApiResponse(data=serializer.data, status=status.HTTP_200_OK)
    except RajOfficer.DoesNotExist:
        return ApiResponse(err="Officer does not exist", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.exception("Error retrieving officer")
        return ApiResponse(err=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
def update_raj_kisan_officer(request):
    """Updates details of an existing officer."""
    officer_id = request.query_params.get('id')
    if not officer_id:
        return ApiResponse(err="Missing officer ID in query parameters",
                           status=status.HTTP_400_BAD_REQUEST)

    try:
        officer = RajOfficer.objects.get(user_id=officer_id)
    except RajOfficer.DoesNotExist:
        return ApiResponse(err="Officer does not exist", status=status.HTTP_404_NOT_FOUND)

    serializer = RajasthanOfficerSerializer(officer, data=request.data, partial=True)

    if serializer.is_valid():
        try:
            serializer.save()
            return ApiResponse(data=serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error updating officer")
            return ApiResponse(err=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return ApiResponse(err=serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
def delete_raj_kisan_officer(request):
    """Deletes an officer by user ID."""
    officer_id = request.query_params.get('id')
    if not officer_id:
        return ApiResponse(err="Missing officer ID in query parameters",
                           status=status.HTTP_400_BAD_REQUEST)

    try:
        officer = RajOfficer.objects.get(user_id=officer_id)
        officer_data = RajasthanOfficerSerializer(officer).data
        officer.delete()
        logger.info("Officer deleted successfully: %s", officer_data.get('userId'))
        return ApiResponse(data="Officer deleted successfully",
                           status=status.HTTP_204_NO_CONTENT)
    except RajOfficer.DoesNotExist:
        return ApiResponse(err="Officer does not exist with id:{id}", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.exception("Error deleting officer")
        return ApiResponse(err=str(e), status=status.HTTP_400_BAD_REQUEST)
