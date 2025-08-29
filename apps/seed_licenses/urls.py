from django.urls import path
from . import views

urlpatterns = [
     # Blockchain Utilities
     path('owner/', views.check_owner_blockchain, name='check-owner'),

     # License Management
     path('license/create/', views.submit_license_application, name='submit-license-application'),
     path('license/count/', views.check_total_license_count, name='license-count'),
     path('license/verify/', views.verify_license_document, name='verify-license-document'),
     path('license/update/', views.update_license_details, name='update-license-details'),
     path('license/<str:license_id>/info/', views.get_license_basic_info, name='license-basic-info'),
     path('license/<str:license_id>/history/', views.get_license_action_history, name='license-action-history'),
     path('license/<str:license_id>/qr/', views.get_license_qr_data, name='license-qr-data'),
     path('license/update-status/', views.update_license_status_view, name='update-license-status'),

     # Smart Contract Metadata
     path('transaction/<str:tx_hash>/', views.transaction_status_view, name='transaction-status'),
     path('contract/address/', views.contract_address_view, name='contract-address'),
     path('contract/methods/', views.contract_methods_view, name='contract-methods'),
]
