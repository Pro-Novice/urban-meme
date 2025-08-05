from django.urls import path
from . import views

app_name = 'seed_license'

urlpatterns = [
     # Blockchain Utilities
     # path('blockchain/initialize/', views.initialize_blockchain_contract, name='initialize-contract'),
     path('blockchain/owner/', views.check_owner_blockchain, name='check-owner'),
     path('blockchain/estimate-gas/', views.estimate_gas_view, name='estimate-gas'),
     path('blockchain/transaction/<str:tx_hash>/', views.transaction_status_view, name='transaction-status'),

     # License Management
     path('blockchain/license/create/', views.submit_license_application, name='submit-license-application'),
     path('blockchain/license/count/', views.check_total_license_count, name='license-count'),
     path('blockchain/license/verify/', views.verify_license_document, name='verify-license-document'),
     path('blockchain/license/update/', views.update_license_details, name='update-license-details'),
     path('blockchain/license/<str:license_id>/info/', views.get_license_basic_info, name='license-basic-info'),
     path('blockchain/license/<str:license_id>/history/', views.get_license_action_history, name='license-action-history'),
     path('blockchain/license/<str:license_id>/qr/', views.get_license_qr_data, name='license-qr-data'),
     path('blockchain/license/update-status/', views.update_license_status_view, name='update-license-status'),

     # Smart Contract Metadata
     path('blockchain/contract/<str:contract_name>/methods/', views.contract_methods_view, name='contract-methods'),
     path('blockchain/contract/<str:contract_name>/abi/', views.contract_abi_view, name='contract-abi'),
     path('blockchain/contract/<str:contract_name>/address/', views.contract_address_view, name='contract-address'),
]
