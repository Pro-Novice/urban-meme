from django.urls import path
from .views import (
    create_license,
    update_license_status,
    get_license,
    verify_license,
    get_certificate_hash,
    add_officer,
    remove_officer
)

urlpatterns = [
    path('blockchain/licenses/create/', create_license, name='create-license'),
    path('blockchain/licenses/<int:license_id>/update-status/', update_license_status, name='update-license-status'),
    path('blockchain/licenses/<int:license_id>/', get_license, name='get-license'),
    path('blockchain/licenses/<int:license_id>/verify/', verify_license, name='verify-license'),
    path('blockchain/licenses/<int:license_id>/hash/', get_certificate_hash, name='get-certificate-hash'),
    path('blockchain/officers/add/', add_officer, name='add-officer'),
    path('blockchain/officers/remove/', remove_officer, name='remove-officer'),
]