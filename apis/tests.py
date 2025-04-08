from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from .models import AgriUser
from .enums import UserType

# Create your tests here.
class UserAuthTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.registration_url = reverse('register')
        self.login_url = reverse('login')
        self.user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "name": "Test User",
            "phone_no": "+919860879034",
            "address": {
                "address": "123 Street",
                "city": "Kanpur",
                "state": "UP",
                "postal_code": "110001",
                "country": "India"
            },
            "aadhaar_no": "123456789012",
            "password": "StrongPass123"
        }

    def test_user_registration_success(self):
        response = self.client.post(self.registration_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertTrue(AgriUser.objects.filter(username="testuser").exists())

    def test_user_registration_missing_field(self):
        data = self.user_data.copy()
        del data['email']
        response = self.client.post(self.registration_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing required fields', response.data['message'])
        
    def test_user_login_success(self):
        self.client.post(self.registration_url, self.user_data, format='json')
        login_data = {
            "username": "testuser",
            "password": "StrongPass123"
        }
        response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data['data']['tokens'])
    # def test_user_registration_invalid_aadhaar(self):
    #     data = self.user_data.copy()
    #     data['aadhaar_no'] = '1234'  # Invalid Aadhaar (too short)

    #     response = self.client.post(self.registration_url, data, format='json')

    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #     self.assertIn('Invalid Aadhaar number format', response.data['message'])

    def test_user_login_invalid_credentials(self):
        login_data = {
            "username": "wronguser",
            "password": "WrongPass"
        }
        response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('Invalid credentials', response.data['message'])
