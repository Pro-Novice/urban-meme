import re

from django.core.exceptions import ValidationError
from rest_framework import serializers

OFFICER_ROLE_MAP = {
    "AGRICULTURE_OFFICER": 0,
    "ASSISTANT_AGRICULTURE_OFFICER": 1,
    "ASSISTANT_DIRECTOR": 2,
    "DEPUTY_DIRECTOR": 3,
    "JOINT_DIRECTOR": 4,
    "JOINT_DIRECTOR_INPUT": 5,
    "FIELD_INSPECTOR": 6,
}

LEVEL_MAP = {
    "STATE": 0,
    "DIVISION": 1,
    "DISTRICT": 2
}
LICENSE_CATEGORY_MAP = {
    "SEED": 0,
    "FERTILIZER": 1,
    "INSECTICIDE": 2
}
from .enums import DivisionEnum, LicenseStatusEnum  # or wherever DivisionEnum is defined

class AddOfficerSerializer(serializers.Serializer):
    officer_address = serializers.CharField()
    officer_name = serializers.CharField()
    officer_id = serializers.CharField()
    officer_role = serializers.CharField()
    department = serializers.CharField()
    officer_level = serializers.CharField()
    state = serializers.CharField(required=False, allow_blank=True)
    district = serializers.CharField(required=False, allow_blank=True)
    division = serializers.CharField(required=False, allow_blank=True)

    def validate_officer_role(self, value):
        enum_val = OFFICER_ROLE_MAP.get(value.upper())
        if enum_val is None:
            raise serializers.ValidationError(f"Invalid officerRole: {value}")
        return enum_val

    def validate_officer_level(self, value):
        enum_val = LEVEL_MAP.get(value.upper())
        if enum_val is None:
            raise serializers.ValidationError(f"Invalid officerLevel: {value} (must be one of {list(LEVEL_MAP.keys())})")
        return enum_val

    def validate_division(self, value):
        if not value:
            return ""
        try:
            # This returns the enum name: e.g., "UDAIPUR"
            return DivisionEnum.from_string(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate(self, data):
        level = data["officer_level"]  # Already enum value
        state = data.get("state", "")
        district = data.get("district", "")
        division = data.get("division", "")

        if level == LEVEL_MAP["STATE"]:
            if not state:
                raise serializers.ValidationError("State is required for STATE level")
            if district or division:
                raise serializers.ValidationError("District and Division must be empty for STATE level")
            data["district"] = ""
            data["division"] = ""

        elif level == LEVEL_MAP["DISTRICT"]:
            if not district:
                raise serializers.ValidationError("District is required for DISTRICT level")
            if state or division:
                raise serializers.ValidationError("State and Division must be empty for DISTRICT level")
            data["state"] = ""
            data["division"] = ""

        elif level == LEVEL_MAP["DIVISION"]:
            if not division:
                raise serializers.ValidationError("Division is required for DIVISION level")
            if state or district:
                raise serializers.ValidationError("State and District must be empty for DIVISION level")
            data["state"] = ""
            data["district"] = ""

            # Convert validated string to actual enum name (e.g., "UDAIPUR")
            if isinstance(data["division"], str):
                try:
                    data["division"] = DivisionEnum.from_string(data["division"])
                except ValueError as e:
                    raise serializers.ValidationError(str(e))

        return data

class CreateLicenseSerializer(serializers.Serializer):
    license_category = serializers.CharField()
    admin_level = serializers.CharField()
    applicant_name = serializers.CharField()
    aadhaar_number = serializers.CharField()
    business_name = serializers.CharField()
    state = serializers.CharField(required=False, allow_blank=True)
    district = serializers.CharField(required=False, allow_blank=True)
    division = serializers.CharField(required=False, allow_blank=True)

    # Optional: If you want to allow string inputs and map to enum
    def validate_license_category(self, value):
        if isinstance(value, str):
            enum_value = LICENSE_CATEGORY_MAP.get(value.upper())
            if enum_value is None:
                raise serializers.ValidationError("Invalid license category")
            return enum_value
        return value

    def validate_admin_level(self, value):
        if isinstance(value, str):
            enum_value = LEVEL_MAP.get(value.upper())
            if enum_value is None:
                raise serializers.ValidationError("Invalid admin level")
            return enum_value
        return value

    def validate_aadhaar_number(self,value):
        """
        Validate the Aadhaar number format to ensure it follows the XXXXXXXXXXXX format.
        """
        if not re.match(r"^[1-9]{1}[0-9]{11}$", value):
            raise ValidationError("Not a valid Aadhaar number. Format: XXXXXXXXXXXX")
    def validate_division(self, value):
        if not value:
            return ""
        try:
            # This returns the enum name: e.g., "UDAIPUR"
            return DivisionEnum.from_string(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate(self, data):
        level = data["admin_level"]  # Already enum value
        state = data.get("state", "")
        district = data.get("district", "")
        division = data.get("division", "")

        if level == LEVEL_MAP["STATE"]:
            if not state:
                raise serializers.ValidationError("State is required for STATE level")
            if district or division:
                raise serializers.ValidationError("District and Division must be empty for STATE level")
            data["district"] = ""
            data["division"] = ""

        elif level == LEVEL_MAP["DISTRICT"]:
            if not district:
                raise serializers.ValidationError("District is required for DISTRICT level")
            if state or division:
                raise serializers.ValidationError("State and Division must be empty for DISTRICT level")
            data["state"] = ""
            data["division"] = ""

        elif level == LEVEL_MAP["DIVISION"]:
            if not division:
                raise serializers.ValidationError("Division is required for DIVISION level")
            if state or district:
                raise serializers.ValidationError("State and District must be empty for DIVISION level")
            data["state"] = ""
            data["district"] = ""

            # Convert validated string to actual enum name (e.g., "UDAIPUR")
            if isinstance(data["division"], str):
                try:
                    data["division"] = DivisionEnum.from_string(data["division"])
                except ValueError as e:
                    raise serializers.ValidationError(str(e))

        return data


class UpdateLicenseStatusSerializer(serializers.Serializer):
    license_id = serializers.IntegerField(min_value=1)
    status = serializers.CharField()
    remarks = serializers.CharField()

    def validate_status(self, value):
        try:
            return LicenseStatusEnum.from_string(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))