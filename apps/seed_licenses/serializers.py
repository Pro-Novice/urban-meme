import re
import base64
from django.conf import settings
from rest_framework import serializers
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

from .enums import (
    LicenseStatusEnum,
    OfficerRole,
    LICENSE_CATEGORY_MAP,
    LEVEL_MAP,
)


# ============================================================
# 1️⃣ Submit License Application Serializer
# ============================================================
class SubmitLicenseApplicationSerializer(serializers.Serializer):
   
    license_number = serializers.CharField()
    license_category = serializers.CharField()
    license_level = serializers.CharField()
    registering_authority = serializers.CharField()
    registering_office_name = serializers.CharField()
    applicant_name = serializers.CharField()
    aadhaar_number = serializers.CharField()
    applicant_permanent_address = serializers.CharField()
    firm_name = serializers.CharField()
    firm_type = serializers.CharField()
    firm_address = serializers.CharField()
    sale_point_address = serializers.CharField()
    sale_storage_address = serializers.CharField()
    production_company = serializers.CharField(required=False, allow_blank=True)
    crop_name = serializers.CharField()
    crop_variety = serializers.CharField()
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)

    def validate_license_number(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("License number cannot be empty.")
        return value.strip()

    def validate_license_category(self, value):
        enum_value = LICENSE_CATEGORY_MAP.get(value.upper())
        if enum_value is None:
            raise serializers.ValidationError(
                f"Invalid license category. Must be one of: {', '.join(LICENSE_CATEGORY_MAP.keys())}."
            )
        return enum_value

    def validate_license_level(self, value):
        enum_value = LEVEL_MAP.get(value.upper())
        if enum_value is None:
            raise serializers.ValidationError(
                f"Invalid license level. Must be one of: {', '.join(LEVEL_MAP.keys())}."
            )
        return enum_value

    def to_internal_value(self, data):
        ret = super().to_internal_value(data)
        # Scale lat/lng to integer micro-degrees for on-chain storage
        for field in ["latitude", "longitude"]:
            if field in ret and ret[field] is not None:
                ret[field] = int(ret[field] * 1_000_000)

        # Drop isSeedSelfProduced unless category is SEED
        if ret["license_category"] != LICENSE_CATEGORY_MAP["SEED"]:
            ret.pop("is_seed_self_produced", None)

        return ret
    def validate(self, attrs):
        category = attrs["license_category"]

        if category in {LICENSE_CATEGORY_MAP["FERTILIZER"], LICENSE_CATEGORY_MAP["PESTICIDE"]}:
            if attrs.get("latitude") is None or attrs.get("longitude") is None:
                raise serializers.ValidationError(
                    "latitude and longitude are required for FERTILIZER and PESTICIDE licenses."
                )
        else:
            # SEED
            attrs.pop("latitude", None)
            attrs.pop("longitude", None)
        return attrs

    def validate_aadhaar_number(self, value):
        """
        Decrypts and validates the Aadhaar number using RSA private key.
        """
        try:
            private_key = serialization.load_pem_private_key(
                settings.GENERATED_PRIVATE_KEY_BYTES,
                password=None,
            )

            encrypted_aadhaar_bytes = base64.b64decode(value)
            decrypted_aadhaar_bytes = private_key.decrypt(
                encrypted_aadhaar_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            aadhaar_plain = decrypted_aadhaar_bytes.decode("utf-8")

            if not re.match(r"^[2-9]{1}[0-9]{11}$", aadhaar_plain):
                raise serializers.ValidationError(
                    "Invalid Aadhaar number format after decryption."
                )

            return aadhaar_plain

        except Exception as e:
            raise serializers.ValidationError(f"Decryption failed: {str(e)}")


# ============================================================
# 2️⃣ Update License Status Serializer
# ============================================================
class UpdateLicenseStatusSerializer(serializers.Serializer):
   
    license_number = serializers.CharField()
    status = serializers.CharField()
    remarks = serializers.CharField()
    officer_name = serializers.CharField()
    role = serializers.CharField()
    renewal_period_days = serializers.IntegerField(min_value=1, required=False)

    def validate_license_number(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("License number cannot be empty.")
        return value.strip()

    def validate_status(self, value):
        try:
            return LicenseStatusEnum.from_string(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_role(self, value):
        try:
            # OfficerRole.from_string() returns int (not Enum)
            return OfficerRole.from_string(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_officer_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Officer name cannot be empty.")
        return value

    def validate_remarks(self, value):
        if not value.strip():
            raise serializers.ValidationError("Remarks cannot be empty.")
        return value

    def validate(self, data):
        status = data.get("status")

        # Renewal period validation
        if status in [
            LicenseStatusEnum.APPROVED.value,
            LicenseStatusEnum.RENEWED.value,
        ]:
            if "renewal_period_days" not in data or data["renewal_period_days"] <= 0:
                raise serializers.ValidationError(
                    {
                        "renewal_period_days": (
                            "Renewal period must be provided and greater than 0 "
                            "when approving or renewing a license."
                        )
                    }
                )

        return data


# ============================================================
# 3️⃣ Verify License Serializer
# ============================================================
class VerifyLicenseSerializer(serializers.Serializer):
    license_number = serializers.CharField()
    expected_hash = serializers.CharField()

    def validate_license_number(self, value):
        if not value.strip():
            raise serializers.ValidationError("License number cannot be empty.")
        return value.strip()

    def validate_expected_hash(self, value):
        if not value.strip():
            raise serializers.ValidationError("Expected hash cannot be empty.")
        return value.strip()


# ============================================================
# 4️⃣ Update License Details Serializer
# ============================================================
class UpdateLicenseDetailsSerializer(serializers.Serializer):

    license_number = serializers.CharField()
    firm_name = serializers.CharField(required=False, allow_blank=True)
    firm_type = serializers.CharField(required=False, allow_blank=True)
    firm_address = serializers.CharField(required=False, allow_blank=True)
    sale_point_address = serializers.CharField(required=False, allow_blank=True)
    sale_storage_address = serializers.CharField(required=False, allow_blank=True)
    production_company = serializers.CharField(required=False, allow_blank=True)
    crop_name = serializers.CharField(required=False, allow_blank=True)
    crop_variety = serializers.CharField(required=False, allow_blank=True)
    role = serializers.CharField()

    def validate_license_number(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("License number cannot be empty.")
        return value.strip()

    def validate_role(self, value):
        try:
            return OfficerRole.from_string(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate(self, data):
        update_fields = [
            "firm_name",
            "firm_type",
            "firm_address",
            "sale_point_address",
            "sale_storage_address",
            "production_company",
            "crop_name",
            "crop_variety",
        ]
        if not any(data.get(field) for field in update_fields):
            raise serializers.ValidationError(
                "At least one field must be provided for update."
            )

        return data

# ============================================================
# 5️⃣ Add Officer Serializer
# ============================================================
class AddOfficerSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=42)
    new_officer_address = serializers.CharField(max_length=42)

    def validate_address(self, value):
        if not isinstance(value, str) or not value.startswith("0x") or len(value) != 42:
            raise serializers.ValidationError("Invalid Ethereum address format for 'address'.")
        return value.lower()

    def validate_new_officer_address(self, value):
        if not isinstance(value, str) or not value.startswith("0x") or len(value) != 42:
            raise serializers.ValidationError("Invalid Ethereum address format for 'new_officer_address'.")
        return value.lower()

    def validate(self, attrs):
        from apps.seed_licenses.services.blockchain.connection import get_default_account
        
        caller_address = attrs.get("address", "").lower()
        new_officer_address = attrs.get("new_officer_address", "").lower()

        # Get admin address from default account
        default_account = get_default_account()
        if not default_account:
            raise serializers.ValidationError(
                {"address": "Admin wallet address not initialized in blockchain configuration."}
            )

        admin_address = default_account["address"].lower()

        if caller_address != admin_address:
            raise serializers.ValidationError(
                {"address": "Access denied. Only the admin wallet can add officers."}
            )
        
        if caller_address == new_officer_address:
            raise serializers.ValidationError(
                {"new_officer_address": "Admin and new officer address cannot be the same."}
            )

        return attrs