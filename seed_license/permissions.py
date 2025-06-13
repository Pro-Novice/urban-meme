from rest_framework.permissions import BasePermission

class IsFarmer(BasePermission):
    message = "Only farmers can perform this action"
    def has_permission(self, request, view):
        return hasattr(request.user, 'has_role') and request.user.has_role("Farmer")

class IsAgricultureOfficer(BasePermission):
    message = "Only agriculture officers can perform this action"
    def has_permission(self, request, view):
        return hasattr(request.user, 'has_role') and request.user.has_role("AGRICULTURE_OFFICER")

class IsDistrictCollector(BasePermission):
    message = "Only district collectors can perform this action"
    def has_permission(self, request, view):
        return hasattr(request.user, 'has_role') and request.user.has_role("DistrictCollector")

class IsSeedCertificationOfficer(BasePermission):
    message = "Only seed certification officers can perform this action"
    def has_permission(self, request, view):
        return hasattr(request.user, 'has_role') and request.user.has_role("SeedCertification")

class IsSubsidyApprovalOfficer(BasePermission):
    message = "Only subsidy approval officers can perform this action"
    def has_permission(self, request, view):
        return hasattr(request.user, 'has_role') and request.user.has_role("SubsidyApprover")

class IsQualityControlOfficer(BasePermission):
    message = "Only quality control officers can perform this action"
    def has_permission(self, request, view):
        return hasattr(request.user, 'has_role') and request.user.has_role("QualityController")

class IsAdmin(BasePermission):
    message = "Only administrators can perform this action"
    def has_permission(self, request, view):
        return hasattr(request.user, 'has_role') and request.user.has_role("Admin")
