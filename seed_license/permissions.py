from rest_framework.permissions import BasePermission


class IsFarmer(BasePermission):
    message = "Only farmers can perform this action"

    def has_permission(self, request, view):
        return request.user.is_farmer


class IsAgricultureOfficer(BasePermission):
    message = "Only agriculture officers can perform this action"

    def has_permission(self, request, view):
        return request.user.is_agriculture_officer


class IsDistrictCollector(BasePermission):
    message = "Only district collectors can perform this action"

    def has_permission(self, request, view):
        return request.user.is_district_collector


class IsSeedCertificationOfficer(BasePermission):
    message = "Only seed certification officers can perform this action"

    def has_permission(self, request, view):
        return request.user.is_seed_certification_officer


class IsSubsidyApprovalOfficer(BasePermission):
    message = "Only subsidy approval officers can perform this action"

    def has_permission(self, request, view):
        return request.user.is_subsidy_approval_officer


class IsQualityControlOfficer(BasePermission):
    message = "Only quality control officers can perform this action"

    def has_permission(self, request, view):
        return request.user.is_quality_control_officer


class IsAdmin(BasePermission):
    message = "Only administrators can perform this action"

    def has_permission(self, request, view):
        return request.user.is_admin