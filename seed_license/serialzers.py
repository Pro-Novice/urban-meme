import re

from django.core.exceptions import ValidationError
from rest_framework import serializers

from .enums import DivisionEnum, LicenseStatusEnum, OfficerRole, LICENSE_CATEGORY_MAP, LEVEL_MAP

# Serializers for license application
class SubmitLicenseApplicationSerializer(serializers.Serializer):
    license_category = serializers.CharField()
    license_level = serializers.CharField()
    applicant_name = serializers.CharField()
    aadhaar_number = serializers.CharField()
    business_name = serializers.CharField()
    business_address = serializers.CharField()
    district = serializers.CharField()
    division = serializers.CharField()

    def validate_license_category(self, value):
        if isinstance(value, str):
            enum_value = LICENSE_CATEGORY_MAP.get(value.upper())
            if enum_value is None:
                raise serializers.ValidationError("Invalid license category")
            return enum_value
        return value

    def validate_license_level(self, value):
        if isinstance(value, str):
            enum_value = LEVEL_MAP.get(value.upper())
            if enum_value is None:
                raise serializers.ValidationError("Invalid license level")
            return enum_value
        return value

    def validate_aadhaar_number(self, value):
        if not re.match(r"^[1-9]{1}[0-9]{11}$", value):
            raise ValidationError("Not a valid Aadhaar number. Format: XXXXXXXXXXXX")
        return value

    def validate_division(self, value):
        if not value:
            return ""
        try:
            return DivisionEnum.from_string(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate(self, data):
        division = data.get("division")
        if division:
            try:
                data["division"] = DivisionEnum.from_string(division)
            except ValueError as e:
                raise serializers.ValidationError({"division": str(e)})

        return data


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

# Serializers for adding inspection feedback
class AddInspectionFeedbackSerializer(serializers.Serializer):
    license_id = serializers.IntegerField(min_value=1)
    inspector = serializers.CharField()
    feedback_type = serializers.IntegerField(min_value=0)
    remarks = serializers.CharField()

    def validate_inspector(self, value):
        if not value.strip():
            raise serializers.ValidationError("Inspector name cannot be empty.")
        return value

    def validate_remarks(self, value):
        if not value.strip():
            raise serializers.ValidationError("Remarks cannot be empty.")
        return value
