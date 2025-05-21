from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from unittest.mock import patch
from seed_license.models import License
from django.utils.timezone import now
import base64
import json

TARGET_VIEW = "seed_license.public_verify.views"  


class PublicVerificationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        License.objects.create(
            license_id=123,
            license_type="SEED_DISTRIBUTION",
            crop_type="Wheat",
            seed_variety="PB-1",
            quantity=100,
            location="Jaipur",
            quality_parameters="High",
            source="AgroCorp Pvt Ltd",
            aadhaar="000000000000",
            blockchain_tx_id="0xabc123",
            status="APPROVED",
        )

        self.mock_payload = {
            "license_id": "123",
            "valid": True,
            "status": "APPROVED",
            "holder_name": "Rohit Kumar",
            "firm_name": "AgroCorp Pvt Ltd",
            "license_type": "SEED_DISTRIBUTION",
            "issue_date": now().date().isoformat(),
            "expiry_date": now().date().isoformat(),
            "verification_time": now().isoformat(),
        }


    @patch(f"{TARGET_VIEW}._verification_payload")
    def test_verify_by_id_success(self, mock_payload):
        mock_payload.return_value = self.mock_payload

        url = reverse("public-verify-license", kwargs={"license_id": 123})
        res = self.client.post(url, {"verification_code": "123"}, format="json")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["license_id"], "123")

    def test_verify_by_id_missing_code(self):
        url = reverse("public-verify-license", kwargs={"license_id": 123})
        res = self.client.post(url, {}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "verification_code required")

    @patch(f"{TARGET_VIEW}._verification_payload")
    def test_verify_by_qr_plain_id(self, mock_payload):
        mock_payload.return_value = self.mock_payload

        url = reverse("public-verify-qr")
        res = self.client.post(url, {"qr_data": "123"}, format="json")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["license_id"], "123")

    @patch(f"{TARGET_VIEW}._verification_payload")
    def test_verify_by_qr_base64_json(self, mock_payload):
        mock_payload.return_value = self.mock_payload
        qr_payload = base64.b64encode(json.dumps({"license_id": 123}).encode()).decode()

        url = reverse("public-verify-qr")
        res = self.client.post(url, {"qr_data": qr_payload}, format="json")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["license_id"], "123")

    def test_verify_by_qr_missing_data(self):
        url = reverse("public-verify-qr")
        res = self.client.post(url, {}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "qr_data required")

    def test_verify_by_qr_invalid_format(self):
        url = reverse("public-verify-qr")
        res = self.client.post(url, {"qr_data": "not-base64"}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "Unsupported QR format")
