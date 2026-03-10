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


def _get_info(client, license_id):
    return client.get(reverse("license-basic-info", args=[license_id]))


def _get_info_by_number(client, license_number):
    return client.get(reverse("license-basic-info-by-number", args=[license_number]))


def _get_count(client):
    resp = client.get(reverse("license-count"))
    assert resp.status_code == 200
    data = resp.json()["data"]
    return data.get("total_licenses", 0) if isinstance(data, dict) else data


# =============================================================================
# Multiple license creation (SEED only — compatible with old tests)
# =============================================================================
@pytest.mark.django_db
class TestMultipleLicenses:

    def test_multiple_seed_licenses_creation(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            for i in range(3):
                payload = {**seed_license_payload,
                           "applicantName": f"Applicant {i+1}",
                           "firmName":      f"Firm {i+1}",
                           "licenseNumber": f"RJSDST-MULTI-{i+1:03d}"}
                resp = _submit(client, payload)
                assert resp.status_code == 202

            assert _get_count(client) == 3

    def test_different_license_states_simultaneously(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            for i in range(4):
                payload = {**seed_license_payload,
                           "applicantName": f"Applicant {i+1}",
                           "firmName":      f"Firm {i+1}",
                           "licenseNumber": f"RJSDST-DIFF-{i+1:03d}"}
                _submit(client, payload)

            assert _get_count(client) == 4

    def test_cross_license_data_isolation(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            licenses = [
                {"applicantName": "First Applicant",  "firmName": "First Firm",
                 "cropName": "Wheat", "licenseNumber": "RJSDST-ISO-001"},
                {"applicantName": "Second Applicant", "firmName": "Second Firm",
                 "cropName": "Rice",  "licenseNumber": "RJSDST-ISO-002"},
            ]
            for lic in licenses:
                _submit(client, {**seed_license_payload, **lic})

            assert _get_count(client) == 2

            # Verify data does not bleed between licenses
            resp1 = _get_info(client, 1)
            resp2 = _get_info(client, 2)
            if resp1.status_code == 200 and resp2.status_code == 200:
                d1 = resp1.json()["data"]
                d2 = resp2.json()["data"]
                assert d1["applicantName"] != d2["applicantName"]
                assert d1["firmName"]      != d2["firmName"]
                assert d1["licenseNumber"] != d2["licenseNumber"]


# =============================================================================
# Mixed-category licenses (new tests)
# =============================================================================
@pytest.mark.django_db
class TestMixedCategoryLicenses:
    """Seed, Fertilizer, Pesticide licenses coexisting."""

    def test_three_category_submissions(
        self, client, seed_license_payload, fertilizer_license_payload,
        pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """All three categories can be submitted in the same session."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            r1 = _submit(client, seed_license_payload)
            r2 = _submit(client, fertilizer_license_payload)
            r3 = _submit(client, pesticide_license_payload)

            assert r1.status_code == 202
            assert r2.status_code == 202
            assert r3.status_code == 202

            assert _get_count(client) == 3

            # Each response has a distinct license number
            nums = {
                r1.json()["data"]["license_number"],
                r2.json()["data"]["license_number"],
                r3.json()["data"]["license_number"],
            }
            assert len(nums) == 3, "All three license numbers must be unique"

    def test_geo_field_isolation_across_categories(
        self, client, seed_license_payload, fertilizer_license_payload,
        pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """SEED must hide lat/lng; FERTILIZER/PESTICIDE must expose them."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)        # id=1
            _submit(client, fertilizer_license_payload)  # id=2
            _submit(client, pesticide_license_payload)   # id=3

            # SEED: no lat/lng
            resp = _get_info(client, 1)
            assert resp.status_code == 200
            info = resp.json()["data"]
            assert "latitude"  not in info, "SEED must NOT expose latitude"
            assert "longitude" not in info, "SEED must NOT expose longitude"

            # FERTILIZER: lat/lng present
            resp = _get_info(client, 2)
            assert resp.status_code == 200
            info = resp.json()["data"]
            assert "latitude"  in info, "FERTILIZER must expose latitude"
            assert "longitude" in info, "FERTILIZER must expose longitude"
            assert info["latitude"]  != 0
            assert info["longitude"] != 0

            # PESTICIDE: lat/lng present
            resp = _get_info(client, 3)
            assert resp.status_code == 200
            info = resp.json()["data"]
            assert "latitude"  in info, "PESTICIDE must expose latitude"
            assert "longitude" in info, "PESTICIDE must expose longitude"
            assert info["latitude"]  != 0
            assert info["longitude"] != 0

    def test_license_id_hidden_across_categories(
        self, client, seed_license_payload, fertilizer_license_payload,
        pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """licenseId must be absent from all category GET responses."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)
            _submit(client, fertilizer_license_payload)
            _submit(client, pesticide_license_payload)

            for lid in (1, 2, 3):
                resp = _get_info(client, lid)
                assert resp.status_code == 200
                assert "licenseId" not in resp.json()["data"], \
                    f"licenseId must be hidden for license {lid}"

    def test_by_number_lookup_all_categories(
        self, client, seed_license_payload, fertilizer_license_payload,
        pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """info-by-number returns correct record for each category."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)
            _submit(client, fertilizer_license_payload)
            _submit(client, pesticide_license_payload)

            cases = [
                (seed_license_payload["licenseNumber"],       "Rajesh Kumar"),
                (fertilizer_license_payload["licenseNumber"], "Suresh Sharma"),
                (pesticide_license_payload["licenseNumber"],  "Mohan Verma"),
            ]
            for lic_num, expected_applicant in cases:
                resp = _get_info_by_number(client, lic_num)
                assert resp.status_code == 200, \
                    f"Expected 200 for {lic_num}, got {resp.status_code}"
                info = resp.json()["data"]
                assert info["applicantName"] == expected_applicant
                assert info["licenseNumber"] == lic_num

    def test_parallel_mixed_category_submissions(
        self, client, seed_license_payload, fertilizer_license_payload,
        pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Submitting multiple licenses of each category should all succeed."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            payloads = []
            for i in range(2):
                payloads.append({**seed_license_payload,
                                 "licenseNumber": f"RJSDST-PAR-{i+1:03d}",
                                 "applicantName": f"Seed Applicant {i+1}"})
            for i in range(2):
                payloads.append({**fertilizer_license_payload,
                                 "licenseNumber": f"RJFTST-PAR-{i+1:03d}",
                                 "applicantName": f"Fertilizer Applicant {i+1}"})
            for i in range(2):
                payloads.append({**pesticide_license_payload,
                                 "licenseNumber": f"RJPSDT-PAR-{i+1:03d}",
                                 "applicantName": f"Pesticide Applicant {i+1}"})

            for payload in payloads:
                resp = _submit(client, payload)
                assert resp.status_code == 202, \
                    f"Expected 202 for {payload['licenseNumber']}, got {resp.status_code}: {resp.json()}"

            assert _get_count(client) == 6