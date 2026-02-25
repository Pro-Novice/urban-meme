from drf_spectacular.utils import (
    extend_schema, extend_schema_view,
    OpenApiParameter, OpenApiExample, OpenApiResponse, inline_serializer
)
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers


# ─────────────────────────────────────────────
# Response serializers for documentation — not used directly in views
# ─────────────────────────────────────────────

class TransactionResponseSerializer(serializers.Serializer):
    transaction_hash = serializers.CharField(help_text="0x-prefixed blockchain tx hash")
    status = serializers.ChoiceField(choices=["accepted", "pending"])
    message = serializers.CharField()
    sender_address = serializers.CharField(required=False, help_text="Only present on license submission")


class NoChangeResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["no_change"])
    message = serializers.CharField()


class LicenseBasicInfoResponseSerializer(serializers.Serializer):
    license_id = serializers.IntegerField()
    license_number = serializers.CharField()
    applicant_name = serializers.CharField()
    category = serializers.ChoiceField(choices=["SEED", "FERTILIZER", "PESTICIDE"])
    level = serializers.ChoiceField(choices=["STATE", "DIVISION", "DISTRICT"])
    status = serializers.ChoiceField(choices=[
        "SUBMITTED", "UNDER_REVIEW", "DOCUMENTS_VERIFIED", "INSPECTION_SCHEDULED",
        "INSPECTION_COMPLETED", "APPROVED", "REJECTED", "REVOKED", "EXPIRED", "RENEWED"
    ])
    firm_name = serializers.CharField()
    firm_type = serializers.CharField()
    firm_address = serializers.CharField()
    sale_point_address = serializers.CharField()
    sale_storage_address = serializers.CharField()
    production_company = serializers.CharField()
    crop_name = serializers.CharField()
    crop_variety = serializers.CharField()
    registering_office_name = serializers.CharField()
    registering_authority = serializers.CharField()
    application_date = serializers.CharField(help_text="e.g. 01 January 2024")
    approval_date = serializers.CharField(allow_null=True, required=False)
    rejection_date = serializers.CharField(allow_null=True, required=False)
    expiry_date = serializers.CharField(allow_null=True, required=False)
    revoked_date = serializers.CharField(allow_null=True, required=False)
    renewal_date = serializers.CharField(allow_null=True, required=False)
    latitude = serializers.FloatField(allow_null=True, required=False,
        help_text="Null for SEED category")
    longitude = serializers.FloatField(allow_null=True, required=False,
        help_text="Null for SEED category")
    is_active = serializers.BooleanField()


class ActionHistoryItemSerializer(serializers.Serializer):
    timestamp = serializers.CharField()
    action_type = serializers.CharField()
    actor_name = serializers.CharField()
    actor_role = serializers.ChoiceField(choices=[
        "CITIZEN", "AGRICULTURE_OFFICER", "ASSISTANT_AGRICULTURE_OFFICER",
        "ASSISTANT_DIRECTOR", "DEPUTY_DIRECTOR", "JOINT_DIRECTOR",
        "JOINT_DIRECTOR_INPUT", "FIELD_INSPECTOR"
    ])
    remarks = serializers.CharField()
    data_hash = serializers.CharField()
    transaction_hash = serializers.CharField(allow_null=True,
        help_text="Matched from EventLog; null if not yet indexed")


class QRDataResponseSerializer(serializers.Serializer):
    verification_hash = serializers.CharField()
    license_number = serializers.CharField()


# ─────────────────────────────────────────────
# License management view schemas
# ─────────────────────────────────────────────

def license_count_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Get total license count",
        description="Reads `licenseIdCounter` from the smart contract.",
        responses={
            200: inline_serializer("LicenseCountResponse", fields={
                "total_licenses": serializers.IntegerField()
            }),
        }
    )


def submit_license_schema():
    from apps.seed_licenses.serializers import SubmitLicenseApplicationSerializer
    return extend_schema(
        tags=["Licenses"],
        summary="Submit a new license application",
        description=(
            "Submits a new application to the blockchain. Returns a `transactionHash` immediately\n\n"
            "**Aadhaar number must be RSA-OAEP encrypted with the server public key before sending.**\n\n"
            "latitude/longitude are required for FERTILIZER and PESTICIDE, ignored for SEED.\n\n"
            "To test for FERTILIZER and PESTICIDE change the licenseCategory field in the example value to either FERTILIZER or PESTICIDE and add latitude and longitude fields with float values."
        ),
        request=SubmitLicenseApplicationSerializer,
        responses={
            202: TransactionResponseSerializer,
            400: OpenApiResponse(description="Validation error (invalid category, level, or Aadhaar decryption failure)"),
            500: OpenApiResponse(description="Blockchain write error"),
        },
        examples=[
            OpenApiExample(
                "Seed License",
                value={
                    "licenseCategory": "SEED",
                    "licenseLevel": "DISTRICT",
                    "registeringAuthority": "State Agriculture Department",
                    "registeringOfficeName": "Jaipur District Office",
                    "applicantName": "Ramesh Kumar",
                    "aadhaarNumber": "<RSA-encrypted-base64>",
                    "applicantPermanentAddress": "12, Gandhi Nagar, Jaipur",
                    "firmName": "Kumar Seeds Pvt Ltd",
                    "firmType": "Private Limited",
                    "firmAddress": "45, Industrial Area, Jaipur",
                    "salePointAddress": "Shop 7, Agri Market, Jaipur",
                    "saleStorageAddress": "Warehouse 3, Jaipur",
                    "productionCompany": "National Seeds Corp",
                    "cropName": "Wheat",
                    "cropVariety": "HD-2967",
                },
                request_only=True,
            ),
        ]
    )


def license_basic_info_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Get license basic info",
        description=(
            "Fetches license details from blockchain via `getLicenseBasicInfo`.\n\n"
        ),
        parameters=[
            OpenApiParameter("license_id", OpenApiTypes.INT, OpenApiParameter.PATH,
                description="Blockchain license ID", required=True)
        ],
        responses={
            200: LicenseBasicInfoResponseSerializer,
            400: OpenApiResponse(description="License ID must be an integer"),
            500: OpenApiResponse(description="Blockchain read error"),
        }
    )


def license_history_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Get license action history",
        description=(
            "Returns all status changes and actions for a license.\n\n"
            "Each item is enriched with `transactionHash` from the local `EventLog` table. "
            "`transactionHash` is `null` if the event hasn't been indexed yet."
        ),
        parameters=[
            OpenApiParameter("license_id", OpenApiTypes.INT, OpenApiParameter.PATH, required=True)
        ],
        responses={
            200: ActionHistoryItemSerializer(many=True),
            400: OpenApiResponse(description="License ID must be an integer"),
            500: OpenApiResponse(description="Blockchain read error"),
        }
    )


def license_qr_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Get license QR verification data",
        description="Returns `verificationHash` and `licenseNumber` for QR generation.",
        parameters=[
            OpenApiParameter("license_id", OpenApiTypes.INT, OpenApiParameter.PATH, required=True)
        ],
        responses={
            200: QRDataResponseSerializer,
            400: OpenApiResponse(description="License ID must be an integer"),
            500: OpenApiResponse(description="Blockchain read error"),
        }
    )


def update_status_schema():
    from apps.seed_licenses.serializers import UpdateLicenseStatusSerializer
    return extend_schema(
        tags=["Licenses"],
        summary="Update license status",
        description=(
            "Updates license lifecycle status. Validates allowed transitions server-side.\n\n"
            "| Current | Allowed Next |\n"
            "|---|---|\n"
            "| SUBMITTED | UNDER_REVIEW |\n"
            "| UNDER_REVIEW | DOCUMENTS_VERIFIED, REJECTED |\n"
            "| DOCUMENTS_VERIFIED | INSPECTION_SCHEDULED |\n"
            "| INSPECTION_SCHEDULED | INSPECTION_COMPLETED |\n"
            "| INSPECTION_COMPLETED | APPROVED, REJECTED |\n"
            "| APPROVED | REVOKED, EXPIRED, RENEWED |\n"
            "| EXPIRED | RENEWED |\n"
            "| RENEWED | EXPIRED, REVOKED |\n"
            "| REJECTED / REVOKED | *(terminal)* |\n\n"
            "`renewalPeriodDays` is required when status is `APPROVED` or `RENEWED`.\n\n"
            "Returns `200 no_change` if license is already in the requested status (no tx sent). "
        ),
        request=UpdateLicenseStatusSerializer,
        responses={
            202: TransactionResponseSerializer,
            200: NoChangeResponseSerializer,
            400: OpenApiResponse(description="Invalid transition or validation error"),
            500: OpenApiResponse(description="Blockchain write error"),
        },
        examples=[
            OpenApiExample(
                "Move to Under Review",
                value={
                    "licenseId": 42,
                    "status": "UNDER_REVIEW",
                    "officerName": "Suresh Singh",
                    "role": "AGRICULTURE_OFFICER",
                    "remarks": "Application received, starting review",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Approve with renewal period",
                value={
                    "licenseId": 42,
                    "status": "APPROVED",
                    "officerName": "Suresh Singh",
                    "role": "JOINT_DIRECTOR",
                    "remarks": "All checks passed",
                    "renewalPeriodDays": 365,
                },
                request_only=True,
            ),
        ]
    )


def verify_document_schema():
    from apps.seed_licenses.serializers import VerifyLicenseSerializer
    return extend_schema(
        tags=["Licenses"],
        summary="Verify license document hash",
        description="Calls `verifyLicenseWithHash` on the contract to confirm document integrity.",
        request=VerifyLicenseSerializer,
        responses={
            202: TransactionResponseSerializer,
            400: OpenApiResponse(description="Validation error"),
            500: OpenApiResponse(description="Blockchain error"),
        }
    )


def update_details_schema():
    from apps.seed_licenses.serializers import UpdateLicenseDetailsSerializer
    return extend_schema(
        tags=["Licenses"],
        summary="Update license firm/crop details",
        description=(
            "Updates mutable license fields via `updateLicenseDetails`. "
            "At least one field besides `licenseId` and `role` must be provided. "
        ),
        request=UpdateLicenseDetailsSerializer,
        responses={
            202: TransactionResponseSerializer,
            400: OpenApiResponse(description="Validation error"),
            500: OpenApiResponse(description="Blockchain error"),
        }
    )


def add_officer_schema():
    from apps.seed_licenses.serializers import AddOfficerSerializer
    return extend_schema(
        tags=["Licenses"],
        summary="Add officer to authorized callers (admin only)",
        description=(
            "Calls `manageAuthorizedApiCallers(address, true)` on the contract.\n\n"
        ),
        request=AddOfficerSerializer,
        responses={
            202: TransactionResponseSerializer,
            400: OpenApiResponse(description="Admin key not found or validation error"),
            500: OpenApiResponse(description="Blockchain error"),
        }
    )


# ─────────────────────────────────────────────
# Blockchain view schemas
# ─────────────────────────────────────────────

def owner_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Get contract owner address",
        description="Reads `owner()` from the deployed contract.",
        responses={
            200: inline_serializer("OwnerResponse", fields={
                "owner": serializers.CharField()
            }),
            400: OpenApiResponse(description="Contract logic error"),
            500: OpenApiResponse(description="Blockchain error"),
        }
    )


def contract_address_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Get deployed contract proxy address",
        responses={
            200: inline_serializer("ContractAddressResponse", fields={
                "contract_address": serializers.CharField()
            }),
            500: OpenApiResponse(description="Error"),
        }
    )


def contract_methods_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="List all ABI methods",
        description="Returns sorted lists of read (view/pure) and write methods from the contract ABI.",
        responses={
            200: inline_serializer("ContractMethodsResponse", fields={
                "read_methods": serializers.ListField(child=serializers.CharField()),
                "write_methods": serializers.ListField(child=serializers.CharField()),
            }),
            500: OpenApiResponse(description="ABI read error"),
        }
    )


def transaction_status_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Get transaction confirmation status",
        description="Returns CONFIRMED, FAILED, or PENDING for a given tx hash.",
        parameters=[
            OpenApiParameter("tx_hash", OpenApiTypes.STR, OpenApiParameter.PATH,
                description="0x-prefixed transaction hash", required=True)
        ],
        responses={
            200: inline_serializer("TxStatusResponse", fields={
                "tx_hash": serializers.CharField(),
                "status": serializers.ChoiceField(choices=["CONFIRMED", "FAILED", "PENDING"]),
                "block_number": serializers.IntegerField(allow_null=True),
                "timestamp": serializers.IntegerField(allow_null=True),
                "confirmations": serializers.IntegerField(allow_null=True),
                "error": serializers.CharField(allow_null=True, required=False),
            }),
            500: OpenApiResponse(description="Error"),
        }
    )


def blockchain_health_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Blockchain node health check",
        description="Checks Web3 connectivity. **Cached 30 seconds.** Returns `healthy` or `degraded`.",
        responses={
            200: inline_serializer("BlockchainHealthResponse", fields={
                "connected": serializers.BooleanField(),
                "status": serializers.ChoiceField(choices=["healthy", "degraded"]),
                "timestamp": serializers.FloatField(),
                "cached": serializers.BooleanField(),
            }),
            500: OpenApiResponse(description="Connection failed"),
        }
    )


def network_info_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Get chain ID, gas price, and latest block number",
        responses={
            200: inline_serializer("NetworkInfoResponse", fields={
                "chain_id": serializers.IntegerField(),
                "gas_price": serializers.IntegerField(help_text="In wei"),
                "block_number": serializers.IntegerField(),
            }),
            400: OpenApiResponse(description="Not connected"),
            500: OpenApiResponse(description="Error"),
        }
    )


def block_details_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Get full block details with decoded transactions",
        parameters=[
            OpenApiParameter("block_number", OpenApiTypes.INT, OpenApiParameter.PATH,
                description="Block number (must be >= 0)", required=True)
        ],
        responses={
            200: OpenApiResponse(description="Block data with decoded transactions"),
            400: OpenApiResponse(description="Invalid block number"),
            500: OpenApiResponse(description="Error"),
        }
    )


def cache_keys_schema():
    return extend_schema(
        tags=["Debug"],
        summary="View Redis cache keys [DEBUG ONLY]",
        description="Lists all Redis keys with `agri_license*` prefix. Do not expose in production.",
        responses={200: OpenApiResponse(description="Cache key listing")}
    )


def cache_clear_schema():
    return extend_schema(
        tags=["Debug"],
        summary="Clear all Redis cache [DEBUG ONLY]",
        responses={200: OpenApiResponse(description="Cache cleared")}
    )


def redis_health_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Redis health check",
        description="Pings Redis, does a set/get round-trip, and returns server info.",
        responses={
            200: inline_serializer("RedisHealthResponse", fields={
                "redis_connected": serializers.BooleanField(),
                "redis_version": serializers.CharField(),
                "connected_clients": serializers.IntegerField(),
                "used_memory_human": serializers.CharField(),
                "total_keys_in_db": serializers.IntegerField(),
                "app_cache_keys": serializers.IntegerField(),
            }),
            500: OpenApiResponse(description="Redis connection failed"),
        }
    )


# ─────────────────────────────────────────────
# Security view schemas
# ─────────────────────────────────────────────

def public_key_schema():
    return extend_schema(
        tags=["Security"],
        summary="Get RSA public key (PEM)",
        description=(
            "Returns the server RSA public key for client-side OAEP encryption of sensitive fields "
            "(e.g. Aadhaar number) before sending to the API."
        ),
        responses={
            200: inline_serializer("PublicKeyResponse", fields={
                "public_key": serializers.CharField(
                    help_text="PEM-encoded RSA public key"
                )
            }),
            500: OpenApiResponse(description="Key not loaded"),
        }
    )


def security_health_schema():
    return extend_schema(
        tags=["Security"],
        summary="RSA keypair health check",
        description="Validates that `private_key.pem` and `public_key.pem` exist and form a valid RSA keypair.",
        responses={
            200: inline_serializer("SecurityHealthResponse", fields={
                "private_key_exists": serializers.BooleanField(),
                "public_key_exists": serializers.BooleanField(),
                "is_valid_rsa_keypair": serializers.BooleanField(),
            }),
            500: OpenApiResponse(description="Key files missing or keypair mismatch"),
        }
    )