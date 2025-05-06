"""Serializer for Rajasthan Kisan Officer Registration"""
from rest_framework import serializers
from Raj_Officer.models import RajOfficer
from user.utils.encryptions import RSAEncryption


class RajasthanOfficerSerializer(serializers.ModelSerializer):
    """
    Serializer for creating Rajasthan Kisan Officer with password validation and hashing.
    """
    confirm_password = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = RajOfficer
        fields = [
            'user_id',
            'name',
            'user_name',
            'mobile_number',
            'email',
            'address',
            'gender',
            'aadhar_number',
            'designation',
            'department',
            'role',
            'password',
            'confirm_password',
        ]
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate(self, data):
        """
        Ensure password and confirm_password match.
        """
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return data

    def create(self, validated_data):
        """
        Create a new RajOfficer instance with encrypted password.
        """
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password')

        crypto = RSAEncryption()
        officer = RajOfficer(**validated_data)
        officer.password_hash = crypto.hash_data(password)
        officer.save()
        return officer
