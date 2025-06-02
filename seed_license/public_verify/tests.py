import json
import hashlib
from datetime import datetime
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from Services.exceptions import BlockchainError


class PublicVerifyAPITests(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.license_id = 123

        
        self._auth_patcher = patch(
            "seed_license.public_verify.views.APIKeyAuthentication.authenticate",
            return_value=(AnonymousUser(), None),
        )
        self._auth_patcher.start()

    def tearDown(self):
        self._auth_patcher.stop()

    
    def test_verify_license_success(self):
        fake_result = (
            True,
            "SEED_PRODUCTION",
            "Ramesh Kumar",
            1_717_000_000,
            1_748_536_000,
        )

        with patch("seed_license.public_verify.views.SeedLicenseHandler") as mh:
            mh.return_value.verify_certificate.return_value = fake_result
            url = reverse("public-verify-license", args=[self.license_id])
            resp = self.client.post(url)

        body = resp.json()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(body["data"]["is_valid"])
        self.assertEqual(body["data"]["license_id"], self.license_id)
        self.assertEqual(body["data"]["license_type"], "SEED_PRODUCTION")
        self.assertIsInstance(body["data"]["approval_date"], str)
        self.assertIsInstance(body["data"]["expiry_date"], str)

    def test_verify_license_blockchain_error(self):
        with patch("seed_license.public_verify.views.SeedLicenseHandler") as mh:
            mh.return_value.verify_certificate.side_effect = BlockchainError("chain down")
            url = reverse("public-verify-license", args=[self.license_id])
            resp = self.client.post(url)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json()["error"], "chain down")

    def test_verify_license_unknown_error(self):
        with patch("seed_license.public_verify.views.SeedLicenseHandler") as mh:
            mh.return_value.verify_certificate.side_effect = Exception("boom")
            url = reverse("public-verify-license", args=[self.license_id])
            resp = self.client.post(url)

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.json()["error"], "boom")

    
    @staticmethod
    def _make_qr_payload(lic_id: int, cert_hash: str):
        """Exact bytes stored in Redis."""
        return json.dumps(
            {
                "license_id": lic_id,
                "certificate_hash": cert_hash,
                "farmer_name": "Ramesh Kumar",
                "approval_date": datetime.utcnow().isoformat(),
            }
        ).encode()

    def test_verify_qr_missing_redis_id(self):
        url = reverse("public-verify-qr")
        resp = self.client.post(url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.json()["error"], "redis_id missing")

    def test_verify_qr_no_payload_in_cache(self):
        with patch("seed_license.public_verify.views.get_redis_connection") as mr:
            mr.return_value.get.return_value = None
            url = reverse("public-verify-qr")
            resp = self.client.post(url, {"redis_id": "abc"}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.json()["error"], "QR credential expired or invalid")

    def test_verify_qr_hash_match_verified(self):
        cert_hash = hashlib.sha256(b"payload").hexdigest()
        payload = self._make_qr_payload(self.license_id, cert_hash)

        stub_redis = MagicMock()
        stub_redis.get.return_value = payload

        with patch(
            "seed_license.public_verify.views.get_redis_connection",
            return_value=stub_redis,
        ), patch(
            "seed_license.public_verify.views.SeedLicenseHandler"
        ) as mh:
            mh.return_value.generate_certificate_hash.return_value = bytes.fromhex(cert_hash)
            url = reverse("public-verify-qr")
            resp = self.client.post(url, {"redis_id": "abc"}, format="json")

        body = resp.json()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED) 
        self.assertEqual(body["data"]["status"], "VERIFIED")
        self.assertEqual(body["data"]["license_id"], self.license_id)
        self.assertEqual(body["data"]["on_chain_hash"], cert_hash)

    def test_verify_qr_hash_mismatch_not_verified(self):
        cert_hash = hashlib.sha256(b"payload").hexdigest()
        payload = self._make_qr_payload(self.license_id, cert_hash)

        stub_redis = MagicMock()
        stub_redis.get.return_value = payload

        with patch(
            "seed_license.public_verify.views.get_redis_connection",
            return_value=stub_redis,
        ), patch(
            "seed_license.public_verify.views.SeedLicenseHandler"
        ) as mh:
            mh.return_value.generate_certificate_hash.return_value = b"\x00" * 32
            url = reverse("public-verify-qr")
            resp = self.client.post(url, {"redis_id": "abc"}, format="json")

        body = resp.json()
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(body["data"]["status"], "NOT_VERIFIED")
