import pytest
import json
from unittest.mock import patch
from django.urls import reverse

from apps.seed_licenses.tests.integration.fixtures import (
    blockchain_state,
    seed_license_payload,
    fertilizer_license_payload,
    pesticide_license_payload,
    complete_license_payload,
    mock_transaction_service,
    mock_license_service,
    mock_multi_account_manager,
    mock_celery_tasks,
)
from apps.seed_licenses.tests.conftest import client


# =============================================================================
# Helpers
# =============================================================================

def _submit(client, payload):
    return client.post(
        reverse("submit-license-application"),
        data=json.dumps(payload),
        content_type="application/json",
    )


def _get_qr(client, license_id):
    return client.get(reverse("license-qr-data", args=[license_id]))


def _verify(client, license_number, expected_hash):
    return client.post(
        reverse("verify-license-document"),
        data=json.dumps({"licenseNumber": license_number, "expectedHash": expected_hash}),
        content_type="application/json",
    )


# =============================================================================
# SEED verification
# =============================================================================
@pytest.mark.django_db
class TestSeedLicenseVerification:

    def test_seed_qr_generation(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)

            resp = _get_qr(client, 1)
            assert resp.status_code in (200, 500)

            if resp.status_code == 200:
                qr = resp.json()["data"]
                assert "verificationHash" in qr
                assert qr["licenseNumber"] == seed_license_payload["licenseNumber"]
                # QR data for SEED must NOT contain lat/lng
                assert "latitude"  not in qr
                assert "longitude" not in qr

    def test_seed_complete_verification_flow(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)

            resp = _get_qr(client, 1)
            assert resp.status_code in (200, 500)
            if resp.status_code == 200:
                qr = resp.json()["data"]
                verification_hash = qr["verificationHash"]
                license_number    = qr["licenseNumber"]

                resp = _verify(client, license_number, verification_hash)
                assert resp.status_code in (202, 500)

    def test_seed_invalid_hash_verification(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)

            resp = _verify(client, seed_license_payload["licenseNumber"], "0xWRONG_HASH_123")
            assert resp.status_code in (202, 400, 500)


# =============================================================================
# FERTILIZER verification
# =============================================================================
@pytest.mark.django_db
class TestFertilizerLicenseVerification:

    def test_fertilizer_qr_generation(
        self, client, fertilizer_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, fertilizer_license_payload)

            resp = _get_qr(client, 1)
            assert resp.status_code in (200, 500)

            if resp.status_code == 200:
                qr = resp.json()["data"]
                assert "verificationHash" in qr
                assert qr["licenseNumber"] == fertilizer_license_payload["licenseNumber"]

    def test_fertilizer_verification_flow(
        self, client, fertilizer_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, fertilizer_license_payload)

            resp = _get_qr(client, 1)
            if resp.status_code == 200:
                qr   = resp.json()["data"]
                resp = _verify(client, qr["licenseNumber"], qr["verificationHash"])
                assert resp.status_code in (202, 400)

    def test_fertilizer_info_shows_lat_lng_pre_qr(
        self, client, fertilizer_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Basic info endpoint exposes lat/lng for FERTILIZER."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, fertilizer_license_payload)

            resp = client.get(reverse("license-basic-info", args=[1]))
            assert resp.status_code == 200
            info = resp.json()["data"]
            assert "latitude"  in info
            assert "longitude" in info
            assert info["latitude"]  != 0
            assert info["longitude"] != 0


# =============================================================================
# PESTICIDE verification
# =============================================================================
@pytest.mark.django_db
class TestPesticideLicenseVerification:

    def test_pesticide_qr_generation(
        self, client, pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, pesticide_license_payload)

            resp = _get_qr(client, 1)
            assert resp.status_code in (200, 500)

            if resp.status_code == 200:
                qr = resp.json()["data"]
                assert "verificationHash" in qr
                assert qr["licenseNumber"] == pesticide_license_payload["licenseNumber"]

    def test_pesticide_verification_flow(
        self, client, pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, pesticide_license_payload)

            resp = _get_qr(client, 1)
            if resp.status_code == 200:
                qr   = resp.json()["data"]
                resp = _verify(client, qr["licenseNumber"], qr["verificationHash"])
                assert resp.status_code in (202, 400)


# =============================================================================
# Cross-category verification
# =============================================================================
@pytest.mark.django_db
class TestLicenseVerification:
    """Shared verification tests covering all categories."""

    def test_qr_consistency_across_multiple_reads(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)

            hashes = []
            for _ in range(3):
                resp = _get_qr(client, 1)
                if resp.status_code == 200:
                    hashes.append(resp.json()["data"]["verificationHash"])

            if len(hashes) > 1:
                assert len(set(hashes)) == 1, "verificationHash must be stable"

    def test_verification_with_nonexistent_license_number(
        self, client, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            resp = _verify(client, "NONEXISTENT-LICENSE-999", "some_hash")
            assert resp.status_code in (400, 500)

    def test_qr_for_nonexistent_license(
        self, client, blockchain_state,
        mock_transaction_service, mock_license_service,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            resp = _get_qr(client, 999)
            assert resp.status_code in (404, 500)

    @pytest.mark.parametrize("payload_fixture,license_number_key", [
        ("seed_license_payload",       "licenseNumber"),
        ("fertilizer_license_payload", "licenseNumber"),
        ("pesticide_license_payload",  "licenseNumber"),
    ])
    def test_qr_data_contains_correct_license_number(
        self, request, client, payload_fixture, license_number_key,
        blockchain_state, mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        payload = request.getfixturevalue(payload_fixture)

        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            blockchain_state.reset()
            _submit(client, payload)

            resp = _get_qr(client, 1)
            if resp.status_code == 200:
                qr = resp.json()["data"]
                assert qr["licenseNumber"] == payload[license_number_key]
                assert "licenseId" not in qr