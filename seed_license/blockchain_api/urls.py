from django.urls import path
from .views import (
    # Admin management
    get_admin, change_admin,
    
    # Officer management
    add_department_officer, remove_department_officer,
    get_officer_role, is_authorized_officer,
    
    # Certificate operations
    generate_certificate_hash, verify_certificate
)

urlpatterns = [
    # Admin management
    path('admin/', get_admin, name='blockchain-admin'),
    path('admin/change/', change_admin, name='blockchain-change-admin'),
    
    # Officer management
    path('officers/add/', add_department_officer, name='blockchain-add-officer'),
    path('officers/remove/', remove_department_officer, name='blockchain-remove-officer'),
    path('officers/<str:officer_address>/role/', get_officer_role, name='blockchain-officer-role'),
    path('officers/<str:officer_address>/is-authorized/', is_authorized_officer, name='blockchain-officer-is-authorized'),
    
    # Certificate operations
    path('certificates/<int:license_id>/hash/', generate_certificate_hash, name='blockchain-certificate-hash'),
    path('certificates/<int:license_id>/verify/', verify_certificate, name='blockchain-certificate-verify'),
]