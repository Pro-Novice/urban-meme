from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from .models import License, BlockchainTransaction 

class BaseAPITestCase(APITestCase):
    """Common setup and helpers for all API test cases."""

    def setUp(self):
        User = get_user_model()
        
        # Create farmer user with appropriate role (adjust based on your actual role system)
        self.farmer = User.objects.create_user(
            username="farmer",
            password="TestUser@123",
            blockchain_address="0xFAKEADDRESS",
            private_key="0xFAKEKEY",
            email="farmer@example.com",
            phone_no='9876543210',
            address={
                "address": "Farm No. 1",
                "city": "rampur",
                "state": "kanpur",
                "postal_code": "389890",
                "country": "India"
            },
            name='Test User',
            aadhaar_no='123456789012',
            role="FARMER"  # Adjust this based on your actual role field
        )
        
        # Create officer user
        self.officer = User.objects.create_user(
            username="officer",
            password="R@ass1234",
            blockchain_address="0xFAKEADDRESS2",
            private_key="0xFAKEKEY2",
            email="officer@example.com",
            name="Officer User",
            phone_no="9876543210",
            address={
                "address": "Farm No. 1",
                "city": "rampur",
                "state": "kanpur",
                "postal_code": "389890",
                "country": "India"
            },
            aadhaar_no="987698769876",
            role="AGRICULTURE_OFFICER"  # Adjust this based on your actual role field
        )
        
        # Create admin user
        self.admin = User.objects.create_user(
            username="admin",
            password="R@ass1234",
            blockchain_address="0xADMIN",
            private_key="0xADMINKEY",
            email="admin@example.com",
            name="Admin User",
            phone_no="5555555555",
            address={
                "address": "Farm No. 1",
                "city": "rampur",
                "state": "kanpur",
                "postal_code": "389890",
                "country": "India"
            },
            aadhaar_no="555555555555",
            role="ADMIN"  # Adjust this based on your actual role field
        )
        self.client = APIClient()

    @staticmethod
    def _fake_receipt(block_number: int = 1, tx_hash: str = "0x" + "a" * 64):
        return SimpleNamespace(
            blockNumber=block_number,
            transactionHash=bytes.fromhex(tx_hash[2:])
        )

    def authenticate(self, user):
        """Force‑authenticate the request as the given user."""
        self.client.force_authenticate(user)


class LicenseApplyTests(BaseAPITestCase):
    """POST /licenses/apply/"""

    url = reverse("license-create")  # name these URLs in your urls.py for easier reversing

    def _valid_payload(self):
        return {
            "name": "Alice",
            "aadhaar": "123412341234",
            "location": "Jaipur",
            "license_type": "SEED_PRODUCTION",
            "seed_variety": "Pusa-1121",
            "crop_type": "Rice",
            "quantity": 100,
            "quality_parameters": "Purity 98%",
            "source": "Self"
        }

    # -------------------- Happy path --------------------

    @patch("licenses.views.Web3")
    @patch("licenses.views.SeedLicenseHandler.apply_for_license")
    def test_apply_license_success(self, mock_apply, mock_web3):
        """Successful license application returns 201 and expected JSON body."""
        # Fake Web3 timestamp lookup
        mock_web3.return_value.eth.get_block.return_value = {"timestamp": int(timezone.now().timestamp())}
        mock_apply.return_value = (
            123,
            self._fake_receipt(block_number=1),
        )

        self.authenticate(self.farmer)
        resp = self.client.post(self.url, self._valid_payload(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        body = resp.data
        self.assertEqual(body["data"]["application_id"], 123)
        self.assertEqual(body["data"]["status"], "APPLIED")
        self.assertIn("blockchain_tx_id", body["data"])
        mock_apply.assert_called_once()

    # ------------------ Validation errors ------------------

    def test_apply_license_missing_fields(self):
        """Omitting required fields should return 400 with a helpful message."""
        payload = {"name": "Bob"}  # clearly insufficient
        self.authenticate(self.farmer)
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Missing required fields", resp.data["err"])

    def test_apply_license_invalid_license_type(self):
        payload = self._valid_payload()
        payload["license_type"] = "NOT_A_TYPE"
        self.authenticate(self.farmer)
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid license_type", resp.data["err"])


class LicenseDetailTests(BaseAPITestCase):
    """GET /licenses/<license_id>/"""

    def setUp(self):
        super().setUp()
        self.url = lambda _id: reverse("license-detail", args=[_id])

    @patch("licenses.views.SeedLicenseHandler.get_license_summary")
    def test_license_detail_success(self, mock_summary):
        summary_payload = {
            "id": 1,
            "name": "Alice",
            "status": 0,
            "license_type": 0,
        }
        mock_summary.return_value = summary_payload
        self.authenticate(self.farmer)
        resp = self.client.get(self.url(1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"], summary_payload)


class LicenseStatusUpdateTests(BaseAPITestCase):
    """POST /licenses/<license_id>/update-status/"""

    def setUp(self):
        super().setUp()
        self.url = lambda _id: reverse("license-status-update", args=[_id])

    @patch("licenses.views.SeedLicenseHandler.update_license_status")
    def test_status_update_success(self, mock_update):
        mock_update.return_value = self._fake_receipt()
        payload = {"status": 1, "remarks": "Looks good"}
        self.authenticate(self.officer)
        resp = self.client.post(self.url(1), payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["status"], 1)

    def test_status_update_unauthorized_role(self):
        """Farmer (not officer) attempting status update should get 403."""
        self.authenticate(self.farmer)
        resp = self.client.post(self.url(1), {"status": 1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_status_update_missing_status(self):
        self.authenticate(self.officer)
        resp = self.client.post(self.url(1), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Missing 'status'", resp.data["err"])


class LicenseStatusViewTests(BaseAPITestCase):
    """GET /licenses/<license_id>/status/"""

    def setUp(self):
        super().setUp()
        self.url = lambda _id: reverse("license-status", args=[_id])

    @patch("licenses.views.SeedLicenseHandler.is_license_valid", return_value=True)
    @patch("licenses.views.SeedLicenseHandler.get_license_status", return_value=3)
    def test_status_view_success(self, mock_status, mock_valid):
        self.authenticate(self.farmer)
        resp = self.client.get(self.url(1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["data"]["blockchain_verified"])
        self.assertEqual(resp.data["data"]["status"], 3)


class LicenseHistoryTests(BaseAPITestCase):
    """GET /licenses/<license_id>/history/"""

    def setUp(self):
        super().setUp()
        self.url = lambda _id: reverse("license-history", args=[_id])

    @patch("licenses.views.SeedLicenseHandler.get_license_history")
    def test_history_success(self, mock_hist):
        hist = [
            {
                "timestamp": int(timezone.now().timestamp()),
                "officer_role": "AGRICULTURE_OFFICER",
                "previous_status": 0,
                "new_status": 1,
                "remarks": "Reviewed",
            }
        ]
        mock_hist.return_value = hist
        self.authenticate(self.farmer)
        resp = self.client.get(self.url(1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"], {"id": 1, "history": hist})


class LicenseCertificateDownloadTests(BaseAPITestCase):
    """GET /licenses/<license_id>/certificate/"""

    def setUp(self):
        super().setUp()
        self.url = lambda _id: reverse("license-certificate", args=[_id])
        # Create a DB license object for fetch
        self.license = License.objects.create(
            applicant=self.farmer,
            license_id=1,
            license_type="SEED_PRODUCTION",
            crop_type="Rice",
            seed_variety="Pusa",
            quantity=100,
            location="Jaipur",
            quality_parameters="Purity 98%",
            source="Self",
            aadhaar="123412341234",
            status="APPROVED",
            blockchain_tx_id="0x" + "b" * 64,
        )

    @patch("licenses.views.SeedLicenseHandler.get_license_summary", return_value={"status": 3})
    @patch("licenses.views.SeedLicenseHandler.get_certificate_url", return_value="https://fake/cert.pdf")
    def test_certificate_success(self, mock_url, mock_summary):
        self.authenticate(self.farmer)
        resp = self.client.get(self.url(1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("certificate_url", resp.data["data"])

    def test_certificate_non_approved(self):
        self.license.status = "APPLIED"
        self.license.save()
        self.authenticate(self.farmer)
        resp = self.client.get(self.url(1))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class LicenseListTests(BaseAPITestCase):
    """GET /licenses/ (farmer‑only)"""

    url = reverse("license-list")

    def setUp(self):
        super().setUp()
        License.objects.bulk_create([
            License(
                applicant=self.farmer,
                license_id=i,
                license_type="SEED_PRODUCTION",
                crop_type="Crop",
                seed_variety="Variety",
                quantity=10,
                location="Loc",
                quality_parameters="Q",
                source="S",
                aadhaar="123412341234",
                status="APPLIED",
                blockchain_tx_id="0x" + str(i).zfill(64),
            ) for i in range(15)
        ])

    def test_license_list_paginated(self):
        self.authenticate(self.farmer)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]["licenses"]), 10)  # default page size
        self.assertEqual(resp.data["results"]["total"], 15)


class TransactionStatusTests(BaseAPITestCase):
    """GET /blockchain/transactions/<tx_hash>/"""

    def setUp(self):
        super().setUp()
        self.url = lambda h: reverse("transaction-status", args=[h])

    @patch("licenses.views.SeedLicenseHandler.get_transaction_info")
    def test_transaction_status_success(self, mock_tx):
        info = {
            "tx_hash": "0xabc",
            "status": "CONFIRMED",
            "block_number": 1,
            "timestamp": int(timezone.now().timestamp()),
            "confirmations": 5,
        }
        mock_tx.return_value = info
        self.authenticate(self.farmer)
        resp = self.client.get(self.url("0xabc"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"], info)


class TransactionHistoryTests(BaseAPITestCase):
    """GET /blockchain/transactions/history/"""

    url = reverse("transaction-history")

    def setUp(self):
        super().setUp()
        # Create 12 fake transactions for pagination test
        lic = License.objects.create(
            applicant=self.farmer,
            license_id=99,
            license_type="SEED_PRODUCTION",
            crop_type="x",
            seed_variety="y",
            quantity=1,
            location="z",
            quality_parameters="q",
            source="s",
            aadhaar="111122223333",
            status="APPLIED",
            blockchain_tx_id="0x" + "d" * 64,
        )
        tx_objects = [
            BlockchainTransaction(
                tx_hash=f"0x{str(i).zfill(64)}",
                block_number=i,
                status="CONFIRMED",
                timestamp=timezone.now(),
                action_type="LICENSE_APPLY",
                license=lic,
                created_by=self.farmer,
            ) for i in range(12)
        ]
        BlockchainTransaction.objects.bulk_create(tx_objects)

    def test_transaction_history_paginated(self):
        self.authenticate(self.farmer)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"]["total"], 12)
        self.assertEqual(len(resp.data["results"]["transactions"]), 10)
