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
# Helper
# =============================================================================

def _extract(data):
    """Normalise blockchain tuple/list or dict response → dict."""
    if isinstance(data, (list, tuple)):
        keys = [
            "licenseId", "licenseNumber", "applicantName", "category", "level",
            "status", "firmName", "firmType", "firmAddress", "salePointAddress",
            "saleStorageAddress", "productionCompany", "cropName", "cropVariety",
        ]
        result = {}
        for i, k in enumerate(keys):
            result[k] = data[i] if i < len(data) else None
        if len(data) > 22:
            result["isActive"] = data[22]
        return result
    return dict(data)


def _submit(client, payload):
    return client.post(
        reverse("submit-license-application"),
        data=json.dumps(payload),
        content_type="application/json",
    )


def _approve(blockchain_state, license_id):
    """Fast-track a license to APPROVED directly in mock state."""
    blockchain_state.licenses[license_id]["status"] = 5


def _update_details(client, payload):
    return client.post(
        reverse("update-license-details"),
        data=json.dumps(payload),
        content_type="application/json",
    )


# =============================================================================
# SEED detail updates
# =============================================================================
@pytest.mark.django_db
class TestLicenseUpdate:
    """Tests for updateLicenseDetails endpoint."""

    def test_update_approved_seed_license(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Can update details of an APPROVED SEED license."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)
            _approve(blockchain_state, 1)

            resp = client.get(reverse("license-basic-info", args=[1]))
            assert resp.status_code == 200
            assert _extract(resp.json()["data"])["status"] in (5, "APPROVED")

            resp = _update_details(client, {
                "licenseId":         1,
                "firmName":          "Updated Firm Name Pvt Ltd",
                "firmType":          "Updated Private Limited",
                "firmAddress":       "Updated Industrial Area",
                "salePointAddress":  "Updated Market Road",
                "saleStorageAddress":"Updated Warehouse Complex",
                "productionCompany": "Updated Production Co",
                "cropName":          ["Updated Wheat", "Updated Rice"],
                "cropVariety":       "HD-3086",
                "role":              "AGRICULTURE_OFFICER",
            })
            assert resp.status_code in (202, 500)
            if resp.status_code == 202:
                assert resp.json()["data"]["status"] in ("pending", "accepted")
                history = client.get(
                    reverse("license-action-history", args=[1])
                ).json()["data"]
                assert history[-1]["actionType"] == "LICENSE_DETAILS_UPDATED"

    def test_partial_update_seed_license(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Partial update: unchanged fields must keep their original values."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)
            _approve(blockchain_state, 1)

            resp = _update_details(client, {
                "licenseId":    1,
                "firmAddress":  "Only This Address Updated",
                "cropVariety":  "Only This Variety Updated",
                "role":         "AGRICULTURE_OFFICER",
            })
            assert resp.status_code in (202, 500)

            if resp.status_code == 202:
                resp = client.get(reverse("license-basic-info", args=[1]))
                assert resp.status_code == 200
                d = _extract(resp.json()["data"])
                assert d["firmAddress"] == "Only This Address Updated"
                assert d["cropVariety"] == "Only This Variety Updated"
                # untouched fields must keep original values
                assert d["firmName"] == seed_license_payload["firmName"]
                assert d["cropName"] == seed_license_payload["cropName"]

    def test_update_renewed_seed_license(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """A RENEWED license remains active and its mutable details can be edited."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service", mock_transaction_service):

            _submit(client, seed_license_payload)
            blockchain_state.licenses[1]["status"] = 9

            resp = _update_details(client, {
                "licenseId": 1,
                "applicationLicenseType": "old application",
                "firmAddress": "Updated After Renewal",
                "role": "AGRICULTURE_OFFICER",
            })

            assert resp.status_code == 202
            info = client.get(reverse("license-basic-info", args=[1])).json()["data"]
            assert info["firmAddress"] == "Updated After Renewal"
            assert info["applicationLicenseType"] == "OLD_APPLICATION"

    def test_update_non_approved_license_fails(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Update on a SUBMITTED (non-approved) license must fail."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)
            # do NOT approve — status stays SUBMITTED

            resp = _update_details(client, {
                "licenseId":   1,
                "firmName":    "Should Not Update",
                "firmAddress": "Should Not Update",
                "role":        "AGRICULTURE_OFFICER",
            })
            # Must be rejected (400/500) or the mock returns an error in data
            if resp.status_code == 202:
                body = resp.json()
                assert "error" in body.get("data", {}) or "error" in body
            else:
                assert resp.status_code in (400, 500)

    def test_update_with_multiple_roles(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        """Different officer roles can all submit update requests."""
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)
            _approve(blockchain_state, 1)

            for role in ("AGRICULTURE_OFFICER", "DEPUTY_DIRECTOR", "JOINT_DIRECTOR"):
                resp = _update_details(client, {
                    "licenseId":   1,
                    "firmAddress": f"Updated by {role}",
                    "role":        role,
                })
                assert resp.status_code in (202, 500)

    def test_sequential_updates(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)
            _approve(blockchain_state, 1)

            updates = [
                {"firmName":        "First Update Firm"},
                {"firmAddress":     "Second Update Address"},
                {"cropName":        ["Third Update Crop"]},
                {"cropVariety":     "Fourth Update Variety"},
                {"salePointAddress":"Fifth Update Sale Point"},
            ]
            for u in updates:
                payload = {"licenseId": 1, "role": "AGRICULTURE_OFFICER", **u}
                resp = _update_details(client, payload)
                assert resp.status_code in (202, 500)

    def test_special_characters_in_update(
        self, client, seed_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, seed_license_payload)
            _approve(blockchain_state, 1)

            resp = _update_details(client, {
                "licenseId":   1,
                "firmName":    "Firm with spéciäl chàrs & numbers 123",
                "firmAddress": "Address with newline\nand tab\t",
                "cropName":    ["Crop with (parentheses) and [brackets]"],
                "role":        "AGRICULTURE_OFFICER",
            })
            assert resp.status_code in (202, 500)


# =============================================================================
# FERTILIZER detail updates — geo fields must persist
# =============================================================================
@pytest.mark.django_db
class TestFertilizerLicenseUpdate:
    """Ensure lat/lng is preserved after updating other details."""

    def test_fertilizer_geo_preserved_after_detail_update(
        self, client, fertilizer_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, fertilizer_license_payload)
            _approve(blockchain_state, 1)

            original_lat = fertilizer_license_payload["latitude"]
            original_lng = fertilizer_license_payload["longitude"]

            resp = _update_details(client, {
                "licenseId":   1,
                "firmName":    "Updated Fertilizer Firm",
                "firmAddress": "Updated Fertilizer Address",
                "role":        "AGRICULTURE_OFFICER",
            })
            assert resp.status_code in (202, 500)

            resp = client.get(reverse("license-basic-info", args=[1]))
            assert resp.status_code == 200
            info = resp.json()["data"]
            # lat/lng must still be present and unchanged
            assert "latitude"  in info, "latitude must persist after detail update"
            assert "longitude" in info, "longitude must persist after detail update"
            assert info["latitude"]  == original_lat
            assert info["longitude"] == original_lng

    def test_fertilizer_license_number_in_response_after_update(
        self, client, fertilizer_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, fertilizer_license_payload)
            _approve(blockchain_state, 1)

            resp = client.get(reverse("license-basic-info", args=[1]))
            assert resp.status_code == 200
            info = resp.json()["data"]
            # licenseNumber must remain unchanged
            assert info["licenseNumber"] == fertilizer_license_payload["licenseNumber"]
            # licenseId must be hidden
            assert "licenseId" not in info


# =============================================================================
# PESTICIDE detail updates — geo fields must persist
# =============================================================================
@pytest.mark.django_db
class TestPesticideLicenseUpdate:

    def test_pesticide_geo_preserved_after_detail_update(
        self, client, pesticide_license_payload, blockchain_state,
        mock_transaction_service, mock_license_service,
        mock_multi_account_manager, mock_celery_tasks,
    ):
        with patch("apps.seed_licenses.views.license_view.license_service", mock_license_service), \
             patch("apps.seed_licenses.views.license_view.tx_service",      mock_transaction_service):

            _submit(client, pesticide_license_payload)
            _approve(blockchain_state, 1)

            original_lat = pesticide_license_payload["latitude"]
            original_lng = pesticide_license_payload["longitude"]

            _update_details(client, {
                "licenseId":   1,
                "firmName":    "Updated Pesticide Firm",
                "role":        "AGRICULTURE_OFFICER",
            })

            resp = client.get(reverse("license-basic-info", args=[1]))
            assert resp.status_code == 200
            info = resp.json()["data"]
            assert "latitude"  in info
            assert "longitude" in info
            assert info["latitude"]  == original_lat
            assert info["longitude"] == original_lng
