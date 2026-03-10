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
    transactionHash = serializers.CharField()
    status          = serializers.CharField(help_text="confirmed | pending | accepted")
    message         = serializers.CharField()
    licenseId       = serializers.IntegerField(required=False, allow_null=True)
    licenseNumber   = serializers.CharField(required=False)
    blockNumber     = serializers.IntegerField(required=False)
    senderAddress   = serializers.CharField(required=False)


class LicenseBasicInfoSerializer(serializers.Serializer):
    licenseId               = serializers.IntegerField()
    licenseNumber           = serializers.CharField()
    licenseCategory         = serializers.CharField()
    licenseLevel            = serializers.CharField()
    status                  = serializers.CharField()
    applicantName           = serializers.CharField()
    firmName                = serializers.CharField()
    firmType                = serializers.CharField()
    firmAddress             = serializers.CharField()
    salePointAddress        = serializers.CharField()
    saleStorageAddress      = serializers.CharField()
    registeringAuthority    = serializers.CharField()
    registeringOfficeName   = serializers.CharField()
    productionCompany       = serializers.CharField()
    cropName                = serializers.CharField()
    cropVariety             = serializers.CharField()
    latitude                = serializers.IntegerField()
    longitude               = serializers.IntegerField()
    createdAt               = serializers.CharField()
    expiresAt               = serializers.CharField()


class ActionHistorySerializer(serializers.Serializer):
    action          = serializers.CharField()
    officerName     = serializers.CharField()
    role            = serializers.CharField()
    timestamp       = serializers.CharField()
    transactionHash = serializers.CharField()
    remarks         = serializers.CharField()


class QRDataSerializer(serializers.Serializer):
    licenseId       = serializers.IntegerField()
    licenseNumber   = serializers.CharField()
    licenseCategory = serializers.CharField()
    status          = serializers.CharField()
    applicantName   = serializers.CharField()
    firmName        = serializers.CharField()
    expiresAt       = serializers.CharField()
    verifyUrl       = serializers.CharField()


class VerifyDocumentResponseSerializer(serializers.Serializer):
    licenseNumber   = serializers.CharField()
    isValid         = serializers.BooleanField()
    expectedHash    = serializers.CharField()
    actualHash      = serializers.CharField()


class NoChangeResponseSerializer(serializers.Serializer):
    status  = serializers.CharField()
    message = serializers.CharField()


# ─────────────────────────────────────────────
# SECURITY
# ─────────────────────────────────────────────

def public_key_schema():
    return extend_schema(
        tags=["Security"],
        summary="Get RSA public key",
        description=(
            "Returns the server RSA public key (PEM format). "
            "The client must encrypt the Aadhaar number using RSA-OAEP with this key "
            "before submitting a license application."
        ),
        responses={
            200: inline_serializer(
                name="PublicKeyResponse",
                fields={"publicKey": serializers.CharField()}
            ),
            500: inline_serializer(
                name="PublicKeyError",
                fields={"error": serializers.CharField()}
            ),
        },
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": {"publicKey": "-----BEGIN PUBLIC KEY-----\nMII..."}},
                response_only=True, status_codes=["200"],
            )
        ]
    )


def security_health_schema():
    return extend_schema(
        tags=["Security"],
        summary="Security health check",
        description="Validates that both RSA private and public key files exist and form a matching keypair.",
        responses={
            200: inline_serializer(
                name="SecurityHealthResponse",
                fields={
                    "privateKeyExists": serializers.BooleanField(),
                    "publicKeyExists":  serializers.BooleanField(),
                    "isValidRsaKeypair": serializers.BooleanField(),
                }
            ),
        },
    )


# ─────────────────────────────────────────────
# LICENSE — CREATE
# ─────────────────────────────────────────────

def submit_license_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Submit a new license application",
        description=(
            "Creates a new license on-chain and waits for confirmation (~2s on QBFT). "
            "Returns the confirmed `licenseId` and `licenseNumber` directly.\n\n"
            "**License categories:** SEED, FERTILIZER, PESTICIDE\n\n"
            "**Rules:**\n"
            "- `latitude` / `longitude` are **required** for FERTILIZER and PESTICIDE\n"
            "- `latitude` / `longitude` must be **omitted** for SEED\n"
            "- `licenseNumber` must be **unique** across all submissions\n"
            "- `aadhaarNumber` must be **RSA-OAEP encrypted** using the public key "
            "from `/api/security/public-key/`\n\n"
            "If confirmation times out, `status` will be `pending` and `licenseId` will be null. "
            "Use `GET /api/transaction/{tx_hash}/` to track."
        ),
        request=inline_serializer(
            name="SubmitLicenseApplication",
            fields={
                "licenseCategory":          serializers.ChoiceField(choices=["SEED", "FERTILIZER", "PESTICIDE"]),
                "licenseLevel":             serializers.ChoiceField(choices=["STATE", "DIVISION", "DISTRICT"]),
                "registeringAuthority":     serializers.CharField(),
                "registeringOfficeName":    serializers.CharField(),
                "licenseNumber":            serializers.CharField(help_text="Must be globally unique. e.g. RJFTST-TEST-001"),
                "applicantName":            serializers.CharField(),
                "aadhaarNumber":            serializers.CharField(help_text="RSA-OAEP encrypted Aadhaar string"),
                "applicantPermanentAddress": serializers.CharField(),
                "firmName":                 serializers.CharField(),
                "firmType":                 serializers.CharField(),
                "firmAddress":              serializers.CharField(),
                "salePointAddress":         serializers.CharField(),
                "saleStorageAddress":       serializers.CharField(),
                "productionCompany":        serializers.CharField(),
                "cropName":                 serializers.CharField(),
                "cropVariety":              serializers.CharField(),
                "latitude":                 serializers.IntegerField(required=False, help_text="Required for FERTILIZER and PESTICIDE only"),
                "longitude":                serializers.IntegerField(required=False, help_text="Required for FERTILIZER and PESTICIDE only"),
            }
        ),
        responses={
            202: TransactionResponseSerializer,
            400: inline_serializer(
                name="SubmitLicenseError",
                fields={"error": serializers.CharField()}
            ),
        },
        examples=[
            OpenApiExample(
                "FERTILIZER example",
                request_only=True,
                value={
                    "licenseCategory": "FERTILIZER",
                    "licenseLevel": "STATE",
                    "registeringAuthority": "Department of Agriculture",
                    "registeringOfficeName": "District Agri Office, Jaipur",
                    "licenseNumber": "RJFTST-TEST-001",
                    "applicantName": "Ravi Kumar",
                    "aadhaarNumber": "<RSA-OAEP-encrypted-string>",
                    "applicantPermanentAddress": "123 Main St, Jaipur",
                    "firmName": "Ravi Fertilizers Pvt Ltd",
                    "firmType": "Private Limited",
                    "firmAddress": "Plot 45, Industrial Area, Jaipur",
                    "salePointAddress": "Shop 12, Market Road",
                    "saleStorageAddress": "Warehouse 3, NH8",
                    "productionCompany": "AgriChem India",
                    "cropName": "Wheat",
                    "cropVariety": "HD-2967",
                    "latitude": 269500,
                    "longitude": 756800,
                }
            ),
            OpenApiExample(
                "PESTICIDE example",
                request_only=True,
                value={
                    "licenseCategory": "PESTICIDE",
                    "licenseLevel": "STATE",
                    "registeringAuthority": "Department of Agriculture",
                    "registeringOfficeName": "District Agri Office, Jaipur",
                    "licenseNumber": "RJPTST-TEST-001",
                    "applicantName": "Ravi Kumar",
                    "aadhaarNumber": "<RSA-OAEP-encrypted-string>",
                    "applicantPermanentAddress": "123 Main St, Jaipur",
                    "firmName": "Ravi Fertilizers Pvt Ltd",
                    "firmType": "Private Limited",
                    "firmAddress": "Plot 45, Industrial Area, Jaipur",
                    "salePointAddress": "Shop 12, Market Road",
                    "saleStorageAddress": "Warehouse 3, NH8",
                    "productionCompany": "AgriChem India",
                    "cropName": "Wheat",
                    "cropVariety": "HD-2967",
                    "latitude": 269500,
                    "longitude": 756800,
                }
            ),
            OpenApiExample(
                "SEED example (no lat/lng)",
                request_only=True,
                value={
                    "licenseCategory": "SEED",
                    "licenseLevel": "STATE",
                    "registeringAuthority": "Department of Agriculture",
                    "registeringOfficeName": "District Agri Office, Jaipur",
                    "licenseNumber": "RJSDST-TEST-003",
                    "applicantName": "Ravi Kumar",
                    "aadhaarNumber": "<RSA-OAEP-encrypted-string>",
                    "applicantPermanentAddress": "123 Main St, Jaipur",
                    "firmName": "Ravi Seeds Pvt Ltd",
                    "firmType": "Private Limited",
                    "firmAddress": "Plot 45, Industrial Area, Jaipur",
                    "salePointAddress": "Shop 12, Market Road",
                    "saleStorageAddress": "Warehouse 3, NH8",
                    "productionCompany": "SeedCorp India",
                    "cropName": "Rice",
                    "cropVariety": "Basmati-370",
                }
            ),
            OpenApiExample(
                "Confirmed response",
                response_only=True, status_codes=["202"],
                value={
                    "success": True,
                    "data": {
                        "transactionHash": "0xb15e...",
                        "status": "confirmed",
                        "message": "License application submitted and confirmed.",
                        "licenseId": 42,
                        "licenseNumber": "RJFTST-TEST-001",
                        "blockNumber": 56530,
                        "senderAddress": "0xFE3B...",
                    }
                }
            ),
            OpenApiExample(
                "Pending (timeout fallback) response",
                response_only=True, status_codes=["202"],
                value={
                    "success": True,
                    "data": {
                        "transactionHash": "0xb15e...",
                        "status": "pending",
                        "message": "Transaction submitted. Poll /transaction/{tx_hash}/ to confirm.",
                        "licenseId": None,
                        "licenseNumber": None,
                        "senderAddress": "0xFE3B...",
                    }
                }
            ),
        ]
    )


# ─────────────────────────────────────────────
# LICENSE — READ
# ─────────────────────────────────────────────

def license_count_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Get total license count",
        description="Returns the total number of licenses ever submitted on-chain.",
        responses={
            200: inline_serializer(
                name="LicenseCountResponse",
                fields={"totalLicenses": serializers.IntegerField()}
            )
        },
    )


def license_basic_info_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Get license info by ID",
        description=(
            "Returns full license details by numeric `licenseId`. "
            "Response is cached in Redis for 30 minutes. Cache is invalidated on status or detail updates."
        ),
        parameters=[
            OpenApiParameter("license_id", OpenApiTypes.INT, OpenApiParameter.PATH, description="Numeric license ID")
        ],
        responses={200: LicenseBasicInfoSerializer},
    )


def license_basic_info_by_number_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Get license info by license number",
        description=(
            "Returns full license details by the human-readable `licenseNumber` (e.g. `RJFTST-TEST-001`). "
            "Response is cached in Redis for 30 minutes."
        ),
        parameters=[
            OpenApiParameter("license_number", OpenApiTypes.STR, OpenApiParameter.PATH,
                             description="Human-readable license number e.g. RJFTST-TEST-001")
        ],
        responses={200: LicenseBasicInfoSerializer},
    )


def license_history_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Get action history by license ID",
        description="Returns the complete on-chain status transition history for a license, enriched with transaction hashes.",
        parameters=[
            OpenApiParameter("license_id", OpenApiTypes.INT, OpenApiParameter.PATH)
        ],
        responses={
            200: inline_serializer(
                name="ActionHistoryResponse",
                fields={"history": ActionHistorySerializer(many=True)}
            )
        },
    )


def license_history_by_number_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Get action history by license number",
        description="Returns the complete on-chain status transition history using the human-readable license number.",
        parameters=[
            OpenApiParameter("license_number", OpenApiTypes.STR, OpenApiParameter.PATH,
                             description="Human-readable license number e.g. RJFTST-TEST-001")
        ],
        responses={
            200: inline_serializer(
                name="ActionHistoryByNumberResponse",
                fields={"history": ActionHistorySerializer(many=True)}
            )
        },
    )


def license_qr_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Get QR verification data",
        description=(
            "Returns the data payload used to generate a QR code for license verification. "
            "Cached in Redis for 30 minutes. Cache is invalidated on status updates."
        ),
        parameters=[
            OpenApiParameter("license_id", OpenApiTypes.INT, OpenApiParameter.PATH)
        ],
        responses={200: QRDataSerializer},
    )


# ─────────────────────────────────────────────
# LICENSE — WRITE
# ─────────────────────────────────────────────

def update_status_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Update license status",
        description=(
            "Advances a license through its lifecycle. "
            "Status transitions are validated server-side.\n\n"
            "**Valid statuses:** SUBMITTED → UNDER_REVIEW → DOCUMENTS_VERIFIED → "
            "INSPECTION_SCHEDULED → INSPECTION_COMPLETED → APPROVED / REJECTED / REVOKED / EXPIRED / RENEWED\n\n"
            "**Rules:**\n"
            "- `renewalPeriodDays` is **required** when status is `APPROVED` or `RENEWED`\n"
            "- `licenseId` OR `licenseNumber` must be provided (not both required — `licenseId` takes precedence)"
        ),
        request=inline_serializer(
            name="UpdateLicenseStatus",
            fields={
                "licenseId":         serializers.IntegerField(required=False, help_text="Numeric ID (preferred)"),
                "licenseNumber":     serializers.CharField(required=False, help_text="Alternative to licenseId"),
                "status":            serializers.ChoiceField(choices=[
                    "SUBMITTED", "UNDER_REVIEW", "DOCUMENTS_VERIFIED",
                    "INSPECTION_SCHEDULED", "INSPECTION_COMPLETED",
                    "APPROVED", "REJECTED", "REVOKED", "EXPIRED", "RENEWED"
                ]),
                "officerName":       serializers.CharField(),
                "role":              serializers.ChoiceField(choices=[
                    "CITIZEN", "AGRICULTURE_OFFICER", "ASSISTANT_AGRICULTURE_OFFICER",
                    "ASSISTANT_DIRECTOR", "DEPUTY_DIRECTOR", "JOINT_DIRECTOR",
                    "JOINT_DIRECTOR_INPUT", "FIELD_INSPECTOR"
                ]),
                "renewalPeriodDays": serializers.IntegerField(required=False, help_text="Required for APPROVED or RENEWED"),
                "remarks":           serializers.CharField(required=False),
            }
        ),
        responses={
            202: TransactionResponseSerializer,
            200: NoChangeResponseSerializer,
            400: inline_serializer(name="UpdateStatusError", fields={"error": serializers.CharField()}),
        },
        examples=[
            OpenApiExample(
                "Move to UNDER_REVIEW",
                request_only=True,
                value={
                    "licenseId": 1,
                    "status": "UNDER_REVIEW",
                    "officerName": "Shrawan",
                    "role": "AGRICULTURE_OFFICER",
                }
            ),
            OpenApiExample(
                "Approve with renewal period",
                request_only=True,
                value={
                    "licenseId": 1,
                    "status": "APPROVED",
                    "officerName": "Shrawan",
                    "role": "JOINT_DIRECTOR",
                    "renewalPeriodDays": 365,
                    "remarks": "All documents verified and inspection passed.",
                }
            ),
        ]
    )


def update_details_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Update license details",
        description=(
            "Updates mutable fields on an existing license. "
            "`licenseId` and `role` are required. At least one optional field must be provided.\n\n"
            "**Updatable fields:** firmName, firmType, firmAddress, salePointAddress, saleStorageAddress, "
            "productionCompany, cropName, cropVariety"
        ),
        request=inline_serializer(
            name="UpdateLicenseDetails",
            fields={
                "licenseId":          serializers.IntegerField(help_text="Required"),
                "role":               serializers.ChoiceField(choices=[
                    "CITIZEN", "AGRICULTURE_OFFICER", "ASSISTANT_AGRICULTURE_OFFICER",
                    "ASSISTANT_DIRECTOR", "DEPUTY_DIRECTOR", "JOINT_DIRECTOR",
                    "JOINT_DIRECTOR_INPUT", "FIELD_INSPECTOR"
                ], help_text="Required"),
                "firmName":           serializers.CharField(required=False),
                "firmType":           serializers.CharField(required=False),
                "firmAddress":        serializers.CharField(required=False),
                "salePointAddress":   serializers.CharField(required=False),
                "saleStorageAddress": serializers.CharField(required=False),
                "productionCompany":  serializers.CharField(required=False),
                "cropName":           serializers.CharField(required=False),
                "cropVariety":        serializers.CharField(required=False),
            }
        ),
        responses={
            202: TransactionResponseSerializer,
            400: inline_serializer(name="UpdateDetailsError", fields={"error": serializers.CharField()}),
        },
    )


def verify_document_schema():
    return extend_schema(
        tags=["Licenses"],
        summary="Verify license document hash",
        description=(
            "Verifies a license's document hash on-chain. "
            "Returns whether the provided `expectedHash` matches the hash stored in the smart contract."
        ),
        request=inline_serializer(
            name="VerifyDocument",
            fields={
                "licenseNumber": serializers.CharField(help_text="Human-readable license number"),
                "expectedHash":  serializers.CharField(help_text="SHA-256 hash of the document to verify"),
            }
        ),
        responses={200: VerifyDocumentResponseSerializer},
        examples=[
            OpenApiExample(
                "Verify example",
                request_only=True,
                value={
                    "licenseNumber": "RJFTST-TEST-001",
                    "expectedHash": "212d02520d33be03153a2c34cb4d50b63f570e6d6881589ebbec2ec6b3da51b0",
                }
            )
        ]
    )


# ─────────────────────────────────────────────
# OFFICERS
# ─────────────────────────────────────────────

def add_officer_schema():
    return extend_schema(
        tags=["Officers"],
        summary="Add an officer to the contract",
        description=(
            "Registers a new officer wallet address on-chain as an authorized caller. "
            "Must be called by the current contract owner or an existing authorized address.\n\n"
            "**Both fields are Ethereum wallet addresses (0x...).**"
        ),
        request=inline_serializer(
            name="AddOfficer",
            fields={
                "address":             serializers.CharField(help_text="Caller's Ethereum address (must be authorized)"),
                "newOfficerAddress":   serializers.CharField(help_text="New officer's Ethereum wallet address"),
            }
        ),
        responses={
            202: TransactionResponseSerializer,
            400: inline_serializer(name="AddOfficerError", fields={"error": serializers.CharField()}),
        },
        examples=[
            OpenApiExample(
                "Add officer example",
                request_only=True,
                value={
                    "address": "0xFE3B557E8Fb62b89F4916B721be55cEb828dBd73",
                    "newOfficerAddress": "0x37e9e9bddc345f82113632a996eefa9b5bdec597",
                }
            )
        ]
    )


# ─────────────────────────────────────────────
# BLOCKCHAIN UTILITIES
# ─────────────────────────────────────────────

def owner_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Get contract owner address",
        description="Returns the Ethereum address of the current UUPS proxy contract owner.",
        responses={
            200: inline_serializer(
                name="OwnerResponse",
                fields={"owner": serializers.CharField()}
            )
        },
    )


def transaction_status_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Get transaction confirmation status",
        description=(
            "Checks whether a submitted transaction has been confirmed on-chain. "
            "Useful as a polling fallback when the submit endpoint returns `status: pending`."
        ),
        parameters=[
            OpenApiParameter("tx_hash", OpenApiTypes.STR, OpenApiParameter.PATH,
                             description="Transaction hash (0x...)")
        ],
        responses={
            200: inline_serializer(
                name="TxStatusResponse",
                fields={
                    "transactionHash": serializers.CharField(),
                    "status":          serializers.ChoiceField(choices=["confirmed", "pending", "accepted", "failed"]),
                    "blockNumber":     serializers.IntegerField(required=False),
                    "gasUsed":         serializers.IntegerField(required=False),
                }
            )
        },
    )


def contract_address_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Get deployed contract address",
        description="Returns the address of the deployed UUPS proxy contract.",
        responses={
            200: inline_serializer(
                name="ContractAddressResponse",
                fields={"contractAddress": serializers.CharField()}
            )
        },
    )


def contract_methods_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="List contract ABI methods",
        description="Returns all read and write method signatures from the contract ABI.",
        responses={
            200: inline_serializer(
                name="ContractMethodsResponse",
                fields={
                    "readMethods":  serializers.ListField(child=serializers.CharField()),
                    "writeMethods": serializers.ListField(child=serializers.CharField()),
                }
            )
        },
    )


def blockchain_health_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Blockchain node health check",
        description="Checks connectivity to the Hyperledger Besu node. Response is cached for 30 seconds.",
        responses={
            200: inline_serializer(
                name="BlockchainHealthResponse",
                fields={
                    "connected":    serializers.BooleanField(),
                    "blockNumber":  serializers.IntegerField(),
                    "chainId":      serializers.IntegerField(),
                    "rpcUrl":       serializers.CharField(),
                }
            )
        },
    )


def network_info_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Blockchain network info",
        description="Returns chain ID, current gas price, latest block number, and connected node URL.",
        responses={
            200: inline_serializer(
                name="NetworkInfoResponse",
                fields={
                    "chainId":      serializers.IntegerField(),
                    "gasPrice":     serializers.CharField(),
                    "blockNumber":  serializers.IntegerField(),
                    "rpcUrl":       serializers.CharField(),
                }
            )
        },
    )


def block_details_schema():
    return extend_schema(
        tags=["Blockchain"],
        summary="Get block details",
        description="Returns full block data including all transactions for the given block number.",
        parameters=[
            OpenApiParameter("block_number", OpenApiTypes.INT, OpenApiParameter.PATH,
                             description="Block number to retrieve")
        ],
        responses={
            200: inline_serializer(
                name="BlockDetailsResponse",
                fields={
                    "blockNumber":   serializers.IntegerField(),
                    "hash":          serializers.CharField(),
                    "timestamp":     serializers.CharField(),
                    "transactions":  serializers.ListField(child=serializers.DictField()),
                }
            )
        },
    )


# ─────────────────────────────────────────────
# CACHE / REDIS (DEBUG)
# ─────────────────────────────────────────────

def cache_keys_schema():
    return extend_schema(
        tags=["Cache (Debug)"],
        summary="View all Redis cache keys",
        description=(
            "Lists all active cache keys matching the `agri_license*` prefix. "
            "⚠️ For debugging only — restrict or remove in production."
        ),
        responses={
            200: inline_serializer(
                name="CacheKeysResponse",
                fields={"keys": serializers.ListField(child=serializers.CharField())}
            )
        },
    )


def cache_clear_schema():
    return extend_schema(
        tags=["Cache (Debug)"],
        summary="Clear all Redis cache",
        description=(
            "Flushes all cache keys matching the `agri_license*` prefix. "
            "⚠️ For debugging only — restrict or remove in production."
        ),
        responses={
            200: inline_serializer(
                name="CacheClearResponse",
                fields={
                    "cleared": serializers.BooleanField(),
                    "message": serializers.CharField(),
                }
            )
        },
    )


def redis_health_schema():
    return extend_schema(
        tags=["Cache (Debug)"],
        summary="Redis health check",
        description="Checks Redis connectivity by performing a ping.",
        responses={
            200: inline_serializer(
                name="RedisHealthResponse",
                fields={
                    "connected": serializers.BooleanField(),
                    "message":   serializers.CharField(),
                }
            )
        },
    )