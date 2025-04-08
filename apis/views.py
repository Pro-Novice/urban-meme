import logging
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import update_last_login
from rest_framework_simplejwt.tokens import RefreshToken
from .models import AgriUser
from django.core.exceptions import ValidationError
from .enums import UserType

logger = logging.getLogger(__name__)

@api_view(['POST'])
def register_user(request):
    try:
        data = request.data
        required_fields = ['username', 'email', 'name', 'phone_no', 'address', 'aadhaar_no', 'password']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return Response({
                'status': 'error',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }, status=status.HTTP_400_BAD_REQUEST)

        if AgriUser.objects.filter(username=data['username']).exists():
            return Response({'status': 'error', 'message': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)

        if AgriUser.objects.filter(email=data['email']).exists():
            return Response({'status': 'error', 'message': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)

        if AgriUser.objects.filter(phone_no=data['phone_no']).exists():
            return Response({'status': 'error', 'message': 'Phone number already exists'}, status=status.HTTP_400_BAD_REQUEST)

        if AgriUser.objects.filter(aadhaar_no=data['aadhaar_no']).exists():
            return Response({'status': 'error', 'message': 'Aadhaar number already exists'}, status=status.HTTP_400_BAD_REQUEST)

        user = AgriUser.objects.create_user(**data)

        return Response({
            'status': 'success',
            'message': 'User registered successfully',
            'data': {
                'user': user.to_dict(),
            }
        }, status=status.HTTP_201_CREATED)

    except ValidationError as e:
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return Response({
            'status': 'error',
            'message': 'Registration failed. Please try again.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def login_user(request):
    try:
        data = request.data
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return Response({
                'status': 'error',
                'message': 'Both username and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)

        if not user:
            return Response({'status': 'error', 'message': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({'status': 'error', 'message': 'User account is inactive'}, status=status.HTTP_403_FORBIDDEN)

        if user.user_type not in [UserType.USER.value, UserType.ADMIN.value]:
            return Response({
                'status': 'error',
                'message': f"Login not allowed for user type: {user.user_type}"
            }, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        update_last_login(None, user)

        return Response({
            'status': 'success',
            'message': f"{user.user_type.capitalize()} login successful",
            'data': {
                'user': user.to_dict(),
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return Response({
            'error': str(e),
            'status': 'error',
            'message': 'Login failed. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
