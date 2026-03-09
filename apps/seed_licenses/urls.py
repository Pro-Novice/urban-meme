from django.urls import path
from . import views

urlpatterns = [
    # ===============================================================
    #  SECURITY ENDPOINTS
    # ===============================================================
    path("security/public-key/", views.get_public_key, name="get-public-key"),

    # ===============================================================
    #  LICENSE MANAGEMENT
    # ===============================================================
    path("license/create/", views.submit_license_application, name="submit-license-application"),
    path("license/count/", views.check_total_license_count, name="license-count"),
    path("license/info/<int:license_id>/", views.get_license_basic_info, name="license-basic-info"),
    path("license/info-by-number/<str:license_number>/", views.get_license_basic_info_by_number, name="license-basic-info-by-number"),
    path("license/history/<int:license_id>/", views.get_license_action_history, name="license-action-history"),
    path("license/history-by-number/<str:license_number>/", views.get_license_action_history_by_number, name="license-action-history-by-number"),
    path("license/qr/<int:license_id>/", views.get_license_qr_data, name="license-qr-data"),

    # License actions
    path("license/update-status/", views.update_license_status_view, name="update-license-status"),
    path("license/mapping/refresh/", views.force_refresh_license_mapping, name="force-refresh-license-mapping"),
    path("license/update/", views.update_license_details, name="update-license-details"),
    path("license/verify/", views.verify_license_document, name="verify-license-document"),

    # ===============================================================
    #  SMART CONTRACT / BLOCKCHAIN UTILITIES
    # ===============================================================
    path("owner/", views.check_owner_blockchain, name="check-owner"),
    path("officers/add/", views.add_officer_to_contract, name="add-officer-to-contract"),
    path("transaction/<str:tx_hash>/", views.transaction_status_view, name="transaction-status"),
    path("contract/address/", views.contract_address_view, name="contract-address"),
    path("contract/methods/", views.contract_methods_view, name="contract-methods"),
    path("health/", views.blockchain_health_check, name="blockchain-health"),
    path("info/", views.blockchain_network_info, name="blockchain-network-info"),
    path("block/<int:block_number>/", views.get_block_details, name="get-block-details"),
    path('cache/view/', views.view_all_cache_keys,name="get-cache-details"),
    path('cache/clear/', views.clear_cache_view,name="get-cache-details"),
    path('blockchain/redis-health/',views.redis_health_check,name="health-cache-details"),

]
