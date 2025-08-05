import re

from django.core.exceptions import ValidationError
from rest_framework import serializers

from .enums import LicenseStatusEnum, OfficerRole, LICENSE_CATEGORY_MAP, LEVEL_MAP

# Serializers for license application
class SubmitLicenseApplicationSerializer(serializers.Serializer):
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

    def validate_license_category(self, value):
        enum_value = LICENSE_CATEGORY_MAP.get(value.upper())
        if enum_value is None:
            raise serializers.ValidationError("Invalid license category")
        return enum_value

    def validate_license_level(self, value):
        enum_value = LEVEL_MAP.get(value.upper())
        if enum_value is None:
            raise serializers.ValidationError("Invalid license level")
        return enum_value

    def validate_aadhaar_number(self, value):
        if not re.match(r"^[1-9]{1}[0-9]{11}$", value):
            raise ValidationError("Invalid Aadhaar number. Must be 12 digits starting with non-zero.")
        return value


# Serializers for updating license status
class UpdateLicenseStatusSerializer(serializers.Serializer):
    license_id = serializers.IntegerField(min_value=1)
    status = serializers.CharField()
    remarks = serializers.CharField()
    officer_name = serializers.CharField()
    role = serializers.CharField()
    renewal_period_days = serializers.IntegerField(min_value=1, required=False)

    def validate_status(self, value):
        try:
            status_enum_value = LicenseStatusEnum.from_string(value)
            return status_enum_value
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_role(self, value):
        try:
            role_enum = OfficerRole.from_string(value)
            return role_enum.value
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

        if status == LicenseStatusEnum.APPROVED.value:
            if "renewal_period_days" not in data or data["renewal_period_days"] <= 0:
                raise serializers.ValidationError({
                    "renewal_period_days": "Renewal period must be provided and greater than 0 when approving a license."
                })

        return data
    

class VerifyLicenseSerializer(serializers.Serializer):
    license_number = serializers.CharField()
    expected_hash = serializers.CharField()

    def validate_expected_hash(self, value):
        if not value.strip():
            raise serializers.ValidationError("Expected hash cannot be empty.")
        return value
    
    def validate_license_number(self, value):
        if not value.strip():
            raise serializers.ValidationError("License number cannot be empty.")
        return value

    def validate(self, data):
        license_id = data.get("license_number")
        expected_hash = data.get("expected_hash")

        if not license_id or not expected_hash:
            raise serializers.ValidationError("Both license ID and expected hash are required.")

        return data


class UpdateLicenseDetailsSerializer(serializers.Serializer):
    license_id = serializers.IntegerField(min_value=1)
    firm_name = serializers.CharField(required=False, allow_blank=True)
    firm_type = serializers.CharField(required=False, allow_blank=True)
    firm_address = serializers.CharField(required=False, allow_blank=True)
    sale_point_address = serializers.CharField(required=False, allow_blank=True)
    sale_storage_address = serializers.CharField(required=False, allow_blank=True)
    production_company = serializers.CharField(required=False, allow_blank=True)
    crop_name = serializers.CharField(required=False, allow_blank=True)
    crop_variety = serializers.CharField(required=False, allow_blank=True)
    role = serializers.CharField()

    def validate_license_id(self, value):
        if value <= 0:
            raise serializers.ValidationError("License ID must be a positive integer.")
        return value
    
    def validate_role(self, value):
        try:
            role_enum = OfficerRole.from_string(value)
            return role_enum.value
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate(self, data):
        license_id = data.get("license_id")
        if not license_id:
            raise serializers.ValidationError("License ID is required.")

        # Ensure at least one field is provided for update
        if not any(data.get(field) for field in [
            "firm_name", "firm_type", "firm_address", 
            "sale_point_address", "sale_storage_address", 
            "production_company", "crop_name", "crop_variety"
        ]):
            raise serializers.ValidationError("At least one field must be provided for update.")

        return data