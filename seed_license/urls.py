from django.urls import path
from . import views


app_name = 'seed_license'

urlpatterns = [
    # ══════════════════════════════════════════════════════════════════
    # Core Blockchain Interaction Endpoints
    # ══════════════════════════════════════════════════════════════════
  
    # Universal write endpoint for any state-changing contract function
    path('blockchain/write/', views.blockchain_write_view, name='blockchain-write'),
    
    # Universal read endpoint for any view/pure contract function
    path('blockchain/read/', views.blockchain_read_view, name='blockchain-read'),
    
    # ══════════════════════════════════════════════════════════════════
    # Transaction Management
    # ══════════════════════════════════════════════════════════════════
    
    # Get transaction status by hash
    path('blockchain/transactions/<str:tx_hash>/', views.transaction_status_view, name='transaction-status'),
    
    # ══════════════════════════════════════════════════════════════════
    # Contract Information & Utilities
    # ══════════════════════════════════════════════════════════════════
    
    # Get available methods (read/write) for a contract
    path('blockchain/contracts/<str:contract_name>/methods/', views.contract_methods_view, name='contract-methods'),
    
    # Get contract ABI
    path('blockchain/contracts/<str:contract_name>/abi/', views.contract_abi_view, name='contract-abi'),
    
    # Get contract address
    path('blockchain/contracts/<str:contract_name>/address/', views.contract_address_view, name='contract-address'),
    
    # Estimate gas for a method call
    path('blockchain/estimate-gas/', views.estimate_gas_view, name='estimate-gas'),

     # Get license basic info
    path("blockchain/license/basic-info/<str:license_id>/", views.get_license_basic_info, name="get-license-basic-info"),

    # verify document hash
    path("blockchain/license/verify-document/", views.verify_document, name="verify-document"),

    # document hash generation and verification
    path("blockchain/license/document-hash/", views.generate_document_hash, name="generate-document-hash"),

    # document status by license ID and document type
    path("blockchain/license/document-status/<str:license_id>/<str:document_type>/", views.get_document_status, name="get-document-status"),

    # Get all document statuses for a license
    path("blockchain/license/document-statuses/<str:license_id>/", views.get_all_document_statuses, name="get-all-document-statuses"),

    # Add inspection feedback
    path("blockchain/license/inspection-feedback/", views.add_inspection_feedback, name="add-inspection-feedback"),

    # Get All Inspection Feedback
    path("blockchain/license/inspection-feedback/<str:license_id>/", views.get_all_inspection_feedback, name="get-all-inspection-feedback"),

    # Get Inspection Feedback by Type
    path("blockchain/license/feedback-count/<str:license_id>/<str:feedback_type>/", views.count_feedback_by_type, name="feedback-count"),
    
    # list all utility functions available in the contract
    path("blockchain/license/utility-functions/", views.list_all_contract_functions, name="list-all-contract-functions"),

    # get license counter
    path("blockchain/license/counter/", views.get_license_counter, name="get-license-counter"),
]