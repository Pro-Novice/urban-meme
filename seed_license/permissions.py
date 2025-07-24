from rest_framework.permissions import BasePermission


class IsFarmer(BasePermission):
    """
    Custom permission to allow only users with 'farmer' role.
    """
    message = "Only farmers can perform this action."

    def has_permission(self, request, view):
        return getattr(request.user, "is_farmer", False)


class IsAgricultureOfficer(BasePermission):
    """
    Custom permission to allow only agriculture officers.
    """
    message = "Only agriculture officers can perform this action."

    def has_permission(self, request, view):
        return getattr(request.user, "is_agriculture_officer", False)


class IsDistrictCollector(BasePermission):
    """
    Custom permission to allow only district collectors.
    """
    message = "Only district collectors can perform this action."

    def has_permission(self, request, view):
        return getattr(request.user, "is_district_collector", False)


class IsSeedCertificationOfficer(BasePermission):
    """
    Custom permission to allow only seed certification officers.
    """
    message = "Only seed certification officers can perform this action."

    def has_permission(self, request, view):
        return getattr(request.user, "is_seed_certification_officer", False)


class IsSubsidyApprovalOfficer(BasePermission):
    """
    Custom permission to allow only subsidy approval officers.
    """
    message = "Only subsidy approval officers can perform this action."

    def has_permission(self, request, view):
        return getattr(request.user, "is_subsidy_approval_officer", False)


class IsQualityControlOfficer(BasePermission):
    """
    Custom permission to allow only quality control officers.
    """
    message = "Only quality control officers can perform this action."

    def has_permission(self, request, view):
        return getattr(request.user, "is_quality_control_officer", False)


class IsAdmin(BasePermission):
    """
    Custom permission to allow only admin users.
    """
    message = "Only administrators can perform this action."

    def has_permission(self, request, view):
        return getattr(request.user, "is_admin", False)
