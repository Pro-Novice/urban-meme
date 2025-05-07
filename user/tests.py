import ast
from rest_framework.test import APITestCase
from django.urls import reverse
from rest_framework import status


class AuthAPITestCase(APITestCase):

    def setUp(self):
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.profile_url = reverse('get_profile')
        self.update_profile_url = reverse('update_profile')
        self.password_reset_url = reverse('request_reset')
        self.password_reset_otp_url = reverse('reset_password')

        self.user_data = {
            'username': 'testuser',
            'email': 'testuser@example.com',
            'name': 'Test User',
            'phone_no': '9876543210',
            "address": {
                "address": "Farm No. 1",
                "city": "rampur",
                "state": "kanpur",
                "postal_code": "389890",
                "country": "India"
            },
            'aadhaar_no': '123456789012',
            'password': 'Testpassword@2',
            'user_type': 'USER'
        }
        response = self.client.post(self.register_url, self.user_data, format='json')

    def test_user_registration_success(self):
        test_data = {
            'username': 'newtestuser',
            'email': 'newtest@example.com',
            'name': 'New Test User',
            'phone_no': '9876543211',
            "address": {
                "address": "Farm No. 2",
                "city": "rampur",
                "state": "kanpur",
                "postal_code": "389891",
                "country": "India"
            },
            'aadhaar_no': '123456789013',
            'password': 'Testpassword@2',
            'user_type': 'USER'
        }
        response = self.client.post(self.register_url, test_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        self.assertIn('data', response_data)
        self.assertIn('user', response_data['data'])

    def test_user_registration_missing_fields(self):
        invalid_data = self.user_data.copy()
        invalid_data.pop('username')
        response = self.client.post(self.register_url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        response_data = response.json()
        self.assertIn('missing_fields', response_data['message'])

    def test_user_login_success(self):
        login_data = {
            "username": "testuser",
            "password": "Testpassword@2",
            "role": "USER"
        }

        response = self.client.post(self.login_url, login_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_login_invalid_credentials(self):
        self.client.post(self.register_url, self.user_data, format='json')
        response = self.client.post(self.login_url, {
            'username': self.user_data['username'],
            'password': 'Wrongpassword'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response_data = response.json()
        self.assertEqual(response_data['message'], 'Invalid credentials')

    def test_user_logout_success(self):
        login_data = {
            "username": "testuser",
            "password": "Testpassword@2",
            "role": "USER"
        }

        login_response = self.client.post(self.login_url, login_data, format='json')

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        tokens = login_response.json().get('data', {}).get('tokens', {})
        access_token = tokens.get('access')
        self.assertIsNotNone(access_token)

        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)
        logout_response = self.client.post(self.logout_url)
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

    def test_user_logout_without_token(self):
        response = self.client.post(self.logout_url)
        response_data = response.json()
        self.assertEqual(response_data['message'], 'Invalid Authorization header format')

    def test_get_user_profile_success(self):
        login_data = {
            "username": "testuser",
            "password": "Testpassword@2"
        }
        login_response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        tokens = login_response.json().get('data', {}).get('tokens', {})
        access_token = tokens.get('access')

        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertIn('user', response_data['data'])

    def test_get_user_profile_unauthorized(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response_data = response.json()
        self.assertEqual(response_data['message'], 'Invalid Authorization header format')

    def test_update_user_profile_invalid_phone(self):
        login_data = {
            "username": "testuser",
            "password": "Testpassword@2"
        }
        login_response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        tokens = login_response.json().get('data', {}).get('tokens', {})
        access_token = tokens.get('access')

        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)
        update_data = {
            'phone_no': 'invalid-phone'
        }
        response = self.client.put(self.update_profile_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        response_data = response.json()
        message = ast.literal_eval(response_data['message'])
        self.assertIn('Invalid phone number', message['phone_no'])

    def test_request_password_reset_success(self):
        data = {'email': 'testuser@example.com'}
        response = self.client.post(self.password_reset_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data['message'], 'OTP sent to email')

    def test_reset_password_with_otp_invalid_otp(self):
        # First request the OTP
        data = {'email': 'testuser@example.com'}
        self.client.post(self.password_reset_url, data, format='json')

        # Reset password with invalid OTP
        reset_data = {
            'email': 'testuser@example.com',
            'otp': 'wrong-otp',  # Invalid OTP
            'new_password': 'NewPassword@123'
        }
        response = self.client.post(self.password_reset_otp_url, reset_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        response_data = response.json()
        self.assertEqual(response_data['message'], 'Invalid or expired OTP')
