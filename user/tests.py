from rest_framework.test import APITestCase
from django.urls import reverse
from rest_framework import status
class AuthAPITestCase(APITestCase):

    def setUp(self):
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')

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
       
