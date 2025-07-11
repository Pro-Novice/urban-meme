from django.urls import path
from . import views


app_name = 'seed_license'

urlpatterns = [

    # ══════════════════════════════════════════════════════════════════
    # Backend Interaction Endpoints
    # ══════════════════════════════════════════════════════════════════
    #Initialize Contract
    path('blockchain/initialize/', views.initialize_blockchain_contract, name='initialize_blockchain_contract'),

    # check owner
    path('blockchain/owner/', views.check_owner_blockchain, name='check_owner_blockchain'),

    # check admin
    path('blockchain/admin/', views.check_admin_blockchain, name='check_admin_blockchain'),

    # count total License
    path('blockchain/license/count/', views.check_total_license_count, name='check_total_license_count'),

    # add officer
    path('blockchain/officer/add/', views.add_officer_view, name='add_officer_view'),

    # get officer role
    path('blockchain/officer/role/<str:address>/', views.get_officer_role, name='get_officer_role'),

    #get officer details
    path('blockchain/officer/details/<str:address>/', views.get_officer_details, name='get_officer_details'),

    #create License
    path('blockchain/license/create/',  views.create_license_view, name='create_license_view'),

    #update license status view
    path('blockchain/license/update-Status/', views.update_license_status_view, name='update_license_status_view'),

    #get license action history
    path('blockchain/license-history/<str:license_id>/', views.get_license_action_history, name='get_license_action_history'),

    # Get license basic info
    path("blockchain/license/basic-info/<str:license_id>/", views.get_license_basic_info,
         name="get-license-basic-info"),

    # verify document hash
    path("blockchain/license/verify-document/", views.verify_document, name="verify-document"),

    # document hash generation and verification
    path("blockchain/license/document-hash/", views.generate_document_hash, name="generate-document-hash"),

    # document status by license ID and document type
    path("blockchain/license/document-status/<str:license_id>/<str:document_type>/", views.get_document_status,
         name="get-document-status"),

    # Get all document statuses for a license
    path("blockchain/license/document-statuses/<str:license_id>/", views.get_all_document_status,
         name="get-all-document-statuses"),

    # Add inspection feedback
    path("blockchain/license/inspection-feedback/", views.add_inspection_feedback, name="add-inspection-feedback"),

    # Get All Inspection Feedback
    path("blockchain/license/inspection-feedback/<str:license_id>/", views.get_all_inspection_feedback,
         name="get-all-inspection-feedback"),

    # Get Inspection Feedback by Type
    path("blockchain/license/feedback-count/<str:license_id>/<str:feedback_type>/", views.count_feedback_by_type,
         name="feedback-count"),

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

]